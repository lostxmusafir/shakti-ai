"""Single local supervisor, with one killable child per job. No cloud fallback."""
import json
import multiprocessing as mp
import time
from pathlib import Path

from sqlalchemy import select, update, func
from .config import Settings
from .db import connect, Dataset, Job, Message, Usage, now
from .storage import read_tables, version_path, write_json


def run_job(settings: Settings, job_id: str):
    engine, sessions = connect(settings)
    try:
        with sessions() as db:
            job = db.get(Job, job_id)
            if not job or job.status != 'running':
                return
            dataset = db.get(Dataset, job.dataset_id)
            if not dataset or dataset.user_id != job.user_id:
                raise ValueError('Dataset is unavailable.')
            payload = json.loads(job.payload)
            if job.kind == 'ingest':
                from .ingestion import parse_file
                tables = parse_file(Path(dataset.original_path), dataset.name)
                if not tables:
                    raise ValueError('No supported table was found.')
                write_json(version_path(settings, dataset.id, 1), tables)
                dataset.version = 1
                dataset.table_count = len(tables)
                dataset.status = 'ready'
                dataset.error = None
                result = {'dataset_id': dataset.id, 'table_count': len(tables)}
            else:
                if dataset.status != 'ready' or payload['version'] != dataset.version:
                    raise ValueError('Dataset changed. Refresh the preview and submit again.')
                tables = read_tables(settings, dataset.id, dataset.version)
                index = payload['table_index']
                if index < 0 or index >= len(tables):
                    raise ValueError('Selected table does not exist.')
                table = tables[index]
                if not table.get('confirmed'):
                    raise ValueError('Review and confirm the table before calculating.')
                from .schemas import AnalysisPlan
                if job.kind == 'question':
                    if dataset.classification != 'synthetic':
                        raise ValueError('Cloud analysis is blocked for Restricted datasets.')
                    day = now()[:10]
                    requests = db.scalar(select(func.count()).select_from(Usage).where(Usage.created_at >= day))
                    if requests >= settings.daily_cloud_limit:
                        raise ValueError('The daily cloud request limit has been reached.')
                    usage = Usage(user_id=job.user_id, failed=1)
                    db.add(usage)
                    db.commit()  # Reserve usage before network call, including crashes/timeouts.
                    from .cloud import generate_plan
                    plan, metrics = generate_plan(settings, payload['question'], table['columns'], classification=dataset.classification)
                    usage.input_tokens = metrics['input_tokens']
                    usage.output_tokens = metrics['output_tokens']
                    usage.latency_ms = metrics['latency_ms']
                    usage.failed = 0
                    db.commit()
                else:
                    plan = AnalysisPlan.model_validate(payload['plan'])
                if plan.clarification:
                    result = {'answer': plan.clarification, 'clarification': True, 'value': None, 'columns': [], 'rows': [],
                              'method': 'Clarification required', 'filters': [], 'source_rows': [], 'row_count': 0,
                              'excluded_rows': 0, 'warnings': []}
                else:
                    from .analysis import analyze
                    result = analyze(table, plan)
                result.update(dataset_name=dataset.name, table_name=table['name'], version=dataset.version,
                              question=payload.get('question', 'Local calculation'),
                              interpretation=plan.interpretation, plan=plan.model_dump(mode='json'))
                db.add(Message(user_id=job.user_id, dataset_id=dataset.id, job_id=job.id,
                               question=payload.get('question', 'Local calculation'), result=json.dumps(result, ensure_ascii=False)))
            job.result = json.dumps(result, ensure_ascii=False, allow_nan=False)
            job.status = 'succeeded'
            job.finished_at = now()
            db.commit()
    except Exception as exc:
        # Validation errors are user safe; unexpected internals must not disclose paths/secrets.
        from pydantic import ValidationError
        if isinstance(exc, ValidationError):
            message = 'The analysis instructions were invalid. Try a clearer question or Local calculation.'
        elif isinstance(exc, ValueError):
            message = str(exc)[:500]
        else:
            message = 'Processing failed. Check file format and installed dependencies, then retry.'
        with sessions() as db:
            job = db.get(Job, job_id)
            if job:
                job.status, job.error, job.finished_at = 'failed', message, now()
                if job.kind == 'ingest':
                    dataset = db.get(Dataset, job.dataset_id)
                    if dataset:
                        dataset.status, dataset.error = 'failed', message
                db.commit()
    finally:
        engine.dispose()


def process_one(settings, sessions, *, isolated=True):
    with sessions() as db:
        job = db.scalar(select(Job).where(Job.status == 'queued').order_by(Job.created_at).limit(1))
        if not job:
            return False
        claimed = db.execute(update(Job).where(Job.id == job.id, Job.status == 'queued').values(status='running'))
        if not claimed.rowcount:
            db.rollback()
            return False
        if job.kind == 'ingest':
            dataset = db.get(Dataset, job.dataset_id)
            if dataset:
                dataset.status = 'running'
        job_id = job.id
        db.commit()
    if isolated:
        child = mp.get_context('spawn').Process(target=run_job, args=(settings, job_id))
        child.start()
        child.join(settings.job_timeout)
        if child.is_alive():
            child.terminate()
            child.join(5)
        with sessions() as db:
            job = db.get(Job, job_id)
            if job and job.status == 'running':
                job.status, job.error, job.finished_at = 'interrupted', 'Processing timed out or stopped. Retry this job.', now()
                if job.kind == 'ingest':
                    dataset = db.get(Dataset, job.dataset_id)
                    if dataset:
                        dataset.status, dataset.error = 'failed', job.error
                db.commit()
    else:
        run_job(settings, job_id)
    return True


def worker_main(settings, stop_event):
    engine, sessions = connect(settings)
    with sessions() as db:
        db.execute(update(Job).where(Job.status == 'running').values(status='interrupted', error='App restarted during processing. Retry this job.'))
        db.execute(update(Dataset).where(Dataset.status == 'running').values(status='failed', error='Import interrupted. Retry the job.'))
        db.commit()
    try:
        while not stop_event.is_set():
            if not process_one(settings, sessions):
                stop_event.wait(0.4)
    finally:
        engine.dispose()
