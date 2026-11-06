import json
import shutil
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.db import Dataset, Job, LoginSession, Message, connect
from app.main import create_app
from app.worker import process_one, worker_main


@pytest.fixture
def test_env():
    tmp = Path(tempfile.mkdtemp(prefix="zydrakon-test-"))
    settings = Settings(data_dir=tmp, job_timeout=30)
    app = create_app(settings, start_worker=False)
    yield settings, app
    shutil.rmtree(tmp, ignore_errors=True)


def test_auth_setup_and_two_user_limit(test_env):
    settings, app = test_env
    with TestClient(app) as client:
        # Check initial setup status
        res = client.get("/api/auth/status")
        assert res.status_code == 200
        assert res.json()["setup_required"] is True
        assert res.json()["users_count"] == 0

        # Create user 1 (Alice)
        r1 = client.post("/api/auth/setup", json={"username": "alice", "password": "Password12345!"})
        assert r1.status_code == 200
        csrf_alice = r1.json()["csrf_token"]
        assert r1.json()["user"]["username"] == "alice"
        assert "zydrakon_session" in r1.cookies

        # Status after 1 user
        res = client.get("/api/auth/status")
        assert res.json()["setup_required"] is False
        assert res.json()["users_count"] == 1

        # Unauthenticated attempt to create user 2 should fail (auth required)
        with TestClient(app) as anonymous_client:
            r_anon = anonymous_client.post("/api/auth/setup", json={"username": "bob", "password": "Password67890!"})
            assert r_anon.status_code == 401

        # Alice creates user 2 (Bob) from Settings
        r2 = client.post("/api/auth/setup", headers={"X-CSRF-Token": csrf_alice}, json={"username": "bob", "password": "Password67890!"})
        assert r2.status_code == 200
        assert r2.json()["user"]["username"] == "bob"

        # Attempt to create user 3 must be blocked with 409
        r3 = client.post("/api/auth/setup", headers={"X-CSRF-Token": r2.json()["csrf_token"]}, json={"username": "charlie", "password": "Password99999!"})
        assert r3.status_code == 409
        assert "two accounts" in r3.json()["detail"]


def test_csrf_and_origin_guards(test_env):
    settings, app = test_env
    with TestClient(app) as client:
        r = client.post("/api/auth/setup", json={"username": "alice", "password": "Password12345!"})
        assert r.status_code == 200

        # Modifying request without CSRF token must fail with 403
        r_no_csrf = client.post("/api/samples")
        assert r_no_csrf.status_code == 403
        assert "Session security check failed" in r_no_csrf.json()["detail"]

        # Modifying request with forged origin must fail with 403
        r_bad_origin = client.post("/api/samples", headers={"X-CSRF-Token": r.json()["csrf_token"], "Origin": "http://evil.com"})
        assert r_bad_origin.status_code == 403
        assert "Cross-origin writes are blocked" in r_bad_origin.json()["detail"]


def test_multi_user_isolation_and_cross_user_denial(test_env):
    settings, app = test_env
    # User 1 (Alice) client
    with TestClient(app) as alice_client:
        r1 = alice_client.post("/api/auth/setup", json={"username": "alice", "password": "Password12345!"})
        csrf_alice = r1.json()["csrf_token"]

        # Alice creates Bob
        alice_client.post("/api/auth/setup", headers={"X-CSRF-Token": csrf_alice}, json={"username": "bob", "password": "Password67890!"})

        # Alice logs back in to verify her session is active
        r_alice_login = alice_client.post("/api/auth/login", json={"username": "alice", "password": "Password12345!"})
        assert r_alice_login.status_code == 200
        csrf_alice = r_alice_login.json()["csrf_token"]

        # Alice uploads sample
        r_sample = alice_client.post("/api/samples", headers={"X-CSRF-Token": csrf_alice})
        assert r_sample.status_code == 202
        dataset_id = r_sample.json()["dataset_id"]
        job_id = r_sample.json()["job_id"]

        # Process Alice's ingest job
        process_one(settings, app.state.sessions, isolated=False)

        # Now Bob logs in on a separate client
        with TestClient(app) as bob_client:
            r_bob_login = bob_client.post("/api/auth/login", json={"username": "bob", "password": "Password67890!"})
            assert r_bob_login.status_code == 200
            csrf_bob = r_bob_login.json()["csrf_token"]

            # Bob cannot see Alice's dataset in datasets list
            r_bob_datasets = bob_client.get("/api/datasets")
            assert r_bob_datasets.status_code == 200
            assert len(r_bob_datasets.json()["datasets"]) == 0

            # Bob cannot preview Alice's dataset
            assert bob_client.get(f"/api/datasets/{dataset_id}/preview").status_code == 404

            # Bob cannot inspect Alice's job
            assert bob_client.get(f"/api/jobs/{job_id}").status_code == 404

            # Bob cannot confirm Alice's dataset
            assert bob_client.post(f"/api/datasets/{dataset_id}/confirm", headers={"X-CSRF-Token": csrf_bob}, json={"table_index": 0, "version": 1}).status_code == 404

            # Bob cannot classify Alice's dataset
            assert bob_client.post(f"/api/datasets/{dataset_id}/classification", headers={"X-CSRF-Token": csrf_bob}, json={"classification": "synthetic", "acknowledge": True}).status_code == 404

            # Bob cannot question Alice's dataset
            assert bob_client.post("/api/questions", headers={"X-CSRF-Token": csrf_bob}, json={"dataset_id": dataset_id, "table_index": 0, "version": 1, "question": "Total?"}).status_code == 404

            # Bob cannot analyze Alice's dataset
            assert bob_client.post("/api/analyses", headers={"X-CSRF-Token": csrf_bob}, json={"dataset_id": dataset_id, "table_index": 0, "version": 1, "plan": {"action": "count"}}).status_code == 404

            # Bob cannot view Alice's conversations
            assert bob_client.get(f"/api/conversations?dataset_id={dataset_id}").status_code == 404

            # Bob cannot delete Alice's dataset
            assert bob_client.delete(f"/api/datasets/{dataset_id}", headers={"X-CSRF-Token": csrf_bob}).status_code == 404


def test_restricted_privacy_gate_zero_outbound_calls(test_env):
    """MANDATORY GATE: Restricted dataset must make 0 outbound cloud calls."""
    settings, app = test_env
    settings.api_key = "test-fake-key"
    with TestClient(app) as client:
        r = client.post("/api/auth/setup", json={"username": "alice", "password": "Password12345!"})
        csrf = r.json()["csrf_token"]

        # Upload sample dataset
        r_samp = client.post("/api/samples", headers={"X-CSRF-Token": csrf})
        dataset_id = r_samp.json()["dataset_id"]
        process_one(settings, app.state.sessions, isolated=False)

        # Confirm the dataset is restricted by default
        preview = client.get(f"/api/datasets/{dataset_id}/preview").json()
        assert preview["dataset"]["classification"] == "restricted"

        # Confirm table
        client.post(f"/api/datasets/{dataset_id}/confirm", headers={"X-CSRF-Token": csrf}, json={"table_index": 0, "version": 1})

        # Spy on OpenAI client to verify zero calls
        with patch("app.cloud.OpenAI") as mock_openai:
            # 1. Asking cloud question on restricted dataset must be rejected at API layer with 403
            r_question = client.post("/api/questions", headers={"X-CSRF-Token": csrf}, json={"dataset_id": dataset_id, "table_index": 0, "version": 2, "question": "What is total revenue?"})
            assert r_question.status_code == 403
            assert "blocked for Restricted data" in r_question.json()["detail"]

            # 2. Direct call to cloud.generate_plan with restricted dataset must raise ValueError
            from app.cloud import generate_plan
            with pytest.raises(ValueError, match="blocked for Restricted"):
                generate_plan(settings, "What is total revenue?", preview["table"]["columns"], classification="restricted")

            # OpenAI client was never instantiated or called
            assert mock_openai.call_count == 0


def test_classification_and_review_gate(test_env):
    settings, app = test_env
    with TestClient(app) as client:
        r = client.post("/api/auth/setup", json={"username": "alice", "password": "Password12345!"})
        csrf = r.json()["csrf_token"]

        r_samp = client.post("/api/samples", headers={"X-CSRF-Token": csrf})
        dataset_id = r_samp.json()["dataset_id"]
        process_one(settings, app.state.sessions, isolated=False)

        # Enforce review gate: calculation before confirmation returns 409
        r_calc_unconfirmed = client.post("/api/analyses", headers={"X-CSRF-Token": csrf}, json={"dataset_id": dataset_id, "table_index": 0, "version": 1, "plan": {"action": "sum", "column": "Revenue"}})
        assert r_calc_unconfirmed.status_code == 409
        assert "Review and confirm" in r_calc_unconfirmed.json()["detail"]

        # Synthetic classification without explicit acknowledgment fails with 422
        r_no_ack = client.post(f"/api/datasets/{dataset_id}/classification", headers={"X-CSRF-Token": csrf}, json={"classification": "synthetic", "acknowledge": False})
        assert r_no_ack.status_code == 422

        # Acknowledged synthetic classification succeeds
        r_ack = client.post(f"/api/datasets/{dataset_id}/classification", headers={"X-CSRF-Token": csrf}, json={"classification": "synthetic", "acknowledge": True})
        assert r_ack.status_code == 200
        assert r_ack.json()["classification"] == "synthetic"


def test_utf16_bom_csv_upload_and_local_calculation(test_env):
    settings, app = test_env
    with TestClient(app) as client:
        r = client.post("/api/auth/setup", json={"username": "alice", "password": "Password12345!"})
        csrf = r.json()["csrf_token"]

        csv_text = "Department,Amount\nSales,100.50\nFinance,200.75\n"
        csv_bytes = csv_text.encode("utf-16")
        r_upload = client.post("/api/uploads", headers={"X-CSRF-Token": csrf}, files={"file": ("metrics.csv", csv_bytes, "text/csv")})
        assert r_upload.status_code == 202
        dataset_id = r_upload.json()["dataset_id"]

        # Process ingest
        process_one(settings, app.state.sessions, isolated=False)

        # Verify preview
        preview = client.get(f"/api/datasets/{dataset_id}/preview").json()
        assert preview["total_rows"] == 2
        assert preview["table"]["columns"][1]["type"] == "number"

        # Confirm table
        r_conf = client.post(f"/api/datasets/{dataset_id}/confirm", headers={"X-CSRF-Token": csrf}, json={"table_index": 0, "version": 1})
        assert r_conf.status_code == 200
        new_version = r_conf.json()["version"]

        # Run sum calculation
        r_calc = client.post("/api/analyses", headers={"X-CSRF-Token": csrf}, json={"dataset_id": dataset_id, "table_index": 0, "version": new_version, "plan": {"action": "sum", "column": "Amount"}})
        assert r_calc.status_code == 202
        calc_job_id = r_calc.json()["job_id"]

        # Process calculation
        process_one(settings, app.state.sessions, isolated=False)

        job = client.get(f"/api/jobs/{calc_job_id}").json()
        assert job["status"] == "succeeded"
        assert job["result"]["value"] == "301.25"


def test_recovery_restart_and_dataset_deletion(test_env):
    settings, app = test_env
    with TestClient(app) as client:
        r = client.post("/api/auth/setup", json={"username": "alice", "password": "Password12345!"})
        csrf = r.json()["csrf_token"]

        r_samp = client.post("/api/samples", headers={"X-CSRF-Token": csrf})
        dataset_id = r_samp.json()["dataset_id"]
        job_id = r_samp.json()["job_id"]

        # Simulate job claimed and marked 'running'
        with app.state.sessions() as db:
            job = db.get(Job, job_id)
            job.status = "running"
            ds = db.get(Dataset, dataset_id)
            ds.status = "running"
            db.commit()

        # Simulate server crash and restart recovery: worker_main startup cleanup
        stop_event = MagicMock()
        stop_event.is_set.return_value = True
        worker_main(settings, stop_event)

        # Verify job is marked 'interrupted' and dataset 'failed'
        job_status = client.get(f"/api/jobs/{job_id}").json()
        assert job_status["status"] == "interrupted"
        assert "restarted" in job_status["error"]

        # User retries the interrupted ingest job
        r_retry = client.post(f"/api/jobs/{job_id}/retry", headers={"X-CSRF-Token": csrf})
        assert r_retry.status_code == 202

        # Worker processes retry
        process_one(settings, app.state.sessions, isolated=False)
        job_done = client.get(f"/api/jobs/{job_id}").json()
        assert job_done["status"] == "succeeded"

        # Now test dataset deletion
        dataset_dir_path = settings.data_dir / "files" / dataset_id
        assert dataset_dir_path.exists()

        r_del = client.delete(f"/api/datasets/{dataset_id}", headers={"X-CSRF-Token": csrf})
        assert r_del.status_code == 200
        assert not dataset_dir_path.exists()

        # Database records removed
        with app.state.sessions() as db:
            assert db.get(Dataset, dataset_id) is None
            assert db.get(Job, job_id) is None
