from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
import hashlib
import io
import json
import multiprocessing as mp
from pathlib import Path
import secrets
import shutil
import time
from typing import Literal
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, FastAPI, File, HTTPException, Query, Request, Response, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import delete, func, select, text, update
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .config import Settings, tesseract_command
from .db import connect, Dataset, Job, LoginSession, Message, Usage, User, now, uid
from .security import check_password, hash_password, token_hash
from .storage import MAX_FILE, dataset_dir, read_tables, validate_upload, version_path, write_json


class StrictBody(BaseModel):
    model_config = ConfigDict(extra='forbid')


class Credentials(StrictBody):
    username: str = Field(min_length=2, max_length=40, pattern=r'^[a-zA-Z0-9_.-]+$')
    password: str = Field(min_length=10, max_length=128)

    @field_validator('username')
    @classmethod
    def normalize(cls, value):
        return value.lower()


class ConfirmRequest(StrictBody):
    table_index: int = Field(ge=0)
    version: int = Field(ge=1)
    rows: list[list[str | int | float | None]] | None = Field(default=None, max_length=50000)


class ClassificationRequest(StrictBody):
    classification: Literal['restricted', 'synthetic']
    acknowledge: bool = False


class QuestionRequest(StrictBody):
    dataset_id: str
    table_index: int = Field(ge=0)
    version: int = Field(ge=1)
    question: str = Field(min_length=2, max_length=2000)


class CalculationRequest(StrictBody):
    dataset_id: str
    table_index: int = Field(ge=0)
    version: int = Field(ge=1)
    plan: dict


def dataset_json(dataset):
    return {key: getattr(dataset, key) for key in ['id', 'name', 'classification', 'status', 'created_at', 'table_count', 'version', 'error', 'job_id']}


def create_app(settings: Settings | None = None, *, start_worker=True):
    settings = settings or Settings.from_env()

    @asynccontextmanager
    async def lifespan(app):
        engine, sessions = connect(settings)
        app.state.engine, app.state.sessions = engine, sessions
        worker = stop = None
        lock_file = None
        if start_worker:
            # A database/worker belongs to one server process. Multiple uvicorn workers
            # would otherwise mark another worker's active jobs as interrupted.
            lock_file = (settings.data_dir / 'app.lock').open('a+b')
            lock_file.seek(0)
            if not lock_file.read(1):
                lock_file.write(b'0')
                lock_file.flush()
            lock_file.seek(0)
            try:
                import os
                if os.name == 'nt':
                    import msvcrt
                    msvcrt.locking(lock_file.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError:
                lock_file.close()
                engine.dispose()
                raise RuntimeError('This data directory is already in use. Run a single app process.') from None
            from .worker import worker_main
            context = mp.get_context('spawn')
            stop = context.Event()
            worker = context.Process(target=worker_main, args=(settings, stop))
            worker.start()
        try:
            yield
        finally:
            if worker:
                stop.set()
                worker.join(6)
                if worker.is_alive():
                    worker.terminate()
                    worker.join(3)
            if lock_file:
                lock_file.close()
            engine.dispose()

    app = FastAPI(title='Zydrakon AI', version='0.1.0', lifespan=lifespan,
                  docs_url='/api/docs', redoc_url=None)
    app.state.settings = settings
    app.state.login_failures = {}
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=['127.0.0.1', 'localhost', 'testserver'])

    @app.middleware('http')
    async def guard(request, call_next):
        if request.method in {'POST', 'PUT', 'PATCH', 'DELETE'}:
            origin = request.headers.get('origin')
            if origin and origin != f'{request.url.scheme}://{request.headers.get("host")}':
                return JSONResponse({'detail': 'Cross-origin writes are blocked.'}, status_code=403)
            length = request.headers.get('content-length')
            try:
                if length and int(length) > 30 * 1024 * 1024:
                    return JSONResponse({'detail': 'Request exceeds the size limit.'}, status_code=413)
            except ValueError:
                return JSONResponse({'detail': 'Invalid request length.'}, status_code=400)
        response = await call_next(request)
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Referrer-Policy'] = 'no-referrer'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['Cache-Control'] = 'no-store'
        response.headers['Content-Security-Policy'] = "default-src 'self'; img-src 'self' blob: data:; style-src 'self' 'unsafe-inline'; script-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'"
        return response

    def get_db(request: Request):
        with request.app.state.sessions() as db:
            yield db

    def auth(request: Request, db=Depends(get_db)):
        token = request.cookies.get('zydrakon_session', '')
        session = db.get(LoginSession, token_hash(token)) if token else None
        if not session or session.expires_at <= now():
            raise HTTPException(401, 'Please sign in.')
        if request.method in {'POST', 'PUT', 'PATCH', 'DELETE'}:
            csrf = request.headers.get('x-csrf-token', '')
            if not secrets.compare_digest(csrf, session.csrf):
                raise HTTPException(403, 'Session security check failed. Refresh and try again.')
        user = db.get(User, session.user_id)
        if not user:
            raise HTTPException(401, 'Please sign in.')
        return user, session

    def owned(db, dataset_id, user_id):
        dataset = db.get(Dataset, dataset_id)
        if not dataset or dataset.user_id != user_id:
            raise HTTPException(404, 'Dataset not found.')
        return dataset

    def table_for(db, body, user):
        dataset = owned(db, body.dataset_id, user.id)
        if dataset.status != 'ready':
            raise HTTPException(409, 'Dataset is not ready.')
        if body.version != dataset.version:
            raise HTTPException(409, 'Dataset changed. Refresh the preview.')
        tables = read_tables(settings, dataset.id, dataset.version)
        if body.table_index >= len(tables):
            raise HTTPException(404, 'Table not found.')
        table = tables[body.table_index]
        if not table.get('confirmed'):
            raise HTTPException(409, 'Review and confirm the table before calculating.')
        return dataset, table

    def new_session(db, user, response, request):
        old = request.cookies.get('zydrakon_session')
        if old:
            old_session = db.get(LoginSession, token_hash(old))
            if old_session and old_session.user_id == user.id:
                db.delete(old_session)
        token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(24)
        db.add(LoginSession(token_hash=token_hash(token), user_id=user.id, csrf=csrf,
                           expires_at=(datetime.now(timezone.utc) + timedelta(hours=settings.session_hours)).isoformat()))
        db.commit()
        response.set_cookie('zydrakon_session', token, max_age=settings.session_hours * 3600,
                            httponly=True, samesite='strict', secure=False, path='/')
        return {'user': {'id': user.id, 'username': user.username}, 'csrf_token': csrf}

    api = APIRouter()

    @api.get('/health')
    def health():
        return {'status': 'ok', 'configured': settings.configured, 'ocr_available': bool(tesseract_command()), 'model': settings.model}

    @api.get('/auth/status')
    def status(db=Depends(get_db)):
        count = db.scalar(select(func.count()).select_from(User))
        return {'setup_required': count == 0, 'users_count': count}

    @api.post('/auth/setup')
    def setup(body: Credentials, request: Request, response: Response, db=Depends(get_db)):
        # Immediate transaction serializes the two-account cap, including first-run races.
        db.execute(text('BEGIN IMMEDIATE'))
        count = db.scalar(select(func.count()).select_from(User))
        if count:
            auth(request, db)
        if count >= 2:
            raise HTTPException(409, 'This pilot supports two accounts.')
        if db.scalar(select(User).where(User.username == body.username)):
            raise HTTPException(409, 'Username already exists.')
        user = User(username=body.username, password_hash=hash_password(body.password))
        db.add(user)
        db.flush()
        return new_session(db, user, response, request)

    @api.post('/auth/login')
    def login(body: Credentials, request: Request, response: Response, db=Depends(get_db)):
        ip = request.client.host if request.client else 'local'
        failures = [t for t in app.state.login_failures.get(ip, []) if time.monotonic() - t < 60]
        app.state.login_failures[ip] = failures
        if len(failures) >= 6:
            raise HTTPException(429, 'Too many attempts. Wait one minute.')
        user = db.scalar(select(User).where(User.username == body.username))
        if not user or not check_password(body.password, user.password_hash):
            failures.append(time.monotonic())
            raise HTTPException(401, 'Invalid username or password.')
        app.state.login_failures[ip] = []
        return new_session(db, user, response, request)

    @api.get('/auth/me')
    def me(current=Depends(auth)):
        user, session = current
        return {'user': {'id': user.id, 'username': user.username}, 'csrf_token': session.csrf}

    @api.post('/auth/logout')
    def logout(response: Response, current=Depends(auth), db=Depends(get_db)):
        db.delete(current[1])
        db.commit()
        response.delete_cookie('zydrakon_session', path='/')
        return {'ok': True}

    @api.get('/datasets')
    def datasets(current=Depends(auth), db=Depends(get_db)):
        values = db.scalars(select(Dataset).where(Dataset.user_id == current[0].id).order_by(Dataset.created_at.desc())).all()
        return {'datasets': [dataset_json(x) for x in values]}

    def save_upload(content, name, user, db):
        # Ignore client paths; keep only a bounded display name.
        name = name.replace('\\', '/').split('/')[-1][:180]
        try:
            validate_upload(name, content)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from None
        dataset_id = uid()
        directory = dataset_dir(settings, dataset_id)
        directory.mkdir(parents=True)
        original = directory / ('original' + Path(name).suffix.lower())
        original.write_bytes(content)
        dataset = Dataset(id=dataset_id, user_id=user.id, name=name, original_path=str(original),
                          sha256=hashlib.sha256(content).hexdigest())
        db.add(dataset)
        db.flush()
        job = Job(user_id=user.id, dataset_id=dataset.id, kind='ingest')
        db.add(job)
        db.flush()
        dataset.job_id = job.id
        db.commit()
        return {'dataset_id': dataset.id, 'job_id': job.id}

    @api.post('/uploads', status_code=202)
    async def upload(file: UploadFile = File(...), current=Depends(auth), db=Depends(get_db)):
        content = await file.read(MAX_FILE + 1)
        await file.close()
        if len(content) > MAX_FILE:
            raise HTTPException(413, 'File exceeds 10 MB.')
        return save_upload(content, file.filename or 'upload', current[0], db)

    @api.post('/samples', status_code=202)
    def sample(current=Depends(auth), db=Depends(get_db)):
        content = ('Date,Department,Product,Revenue,Cost,Units\n'
                   '2026-10-01,Sales,Atlas,12500.50,8000.00,25\n'
                   '2026-10-02,Operations,Nova,8400.00,5000.00,14\n'
                   '2026-10-03,Sales,Nova,15600.00,9200.00,26\n'
                   '2026-10-04,Finance,Atlas,6300.00,4100.00,12\n'
                   '2026-10-05,HR,Orbit,4200.00,2900.00,7\n'
                   '2026-10-06,Operations,Orbit,9800.00,6400.00,16\n'
                   '2026-10-07,Sales,Atlas,11200.00,7300.00,22\n'
                   '2026-10-08,Finance,Nova,7600.00,4800.00,13\n').encode()
        return save_upload(content, 'Synthetic_company_data.csv', current[0], db)

    @api.get('/datasets/{dataset_id}/preview')
    def preview(dataset_id: str, table_index: int = Query(0, ge=0), offset: int = Query(0, ge=0),
                limit: int = Query(100, ge=1, le=500), current=Depends(auth), db=Depends(get_db)):
        dataset = owned(db, dataset_id, current[0].id)
        if dataset.status != 'ready':
            raise HTTPException(409, dataset.error or 'File is still processing.')
        tables = read_tables(settings, dataset_id, dataset.version)
        if table_index >= len(tables):
            raise HTTPException(404, 'Table not found.')
        table = dict(tables[table_index])
        count = len(table['rows'])
        table['rows'] = table['rows'][offset:offset + limit]
        table['source_rows'] = table['source_rows'][offset:offset + limit]
        return {'dataset': dataset_json(dataset), 'table': table, 'table_names': [t['name'] for t in tables],
                'version': dataset.version, 'total_rows': count}

    @api.get('/datasets/{dataset_id}/image')
    def image(dataset_id: str, current=Depends(auth), db=Depends(get_db)):
        dataset = owned(db, dataset_id, current[0].id)
        ext = Path(dataset.original_path).suffix.lower()
        if ext not in {'.png', '.jpg', '.jpeg'}:
            raise HTTPException(404, 'No image for this dataset.')
        return FileResponse(dataset.original_path, media_type='image/png' if ext == '.png' else 'image/jpeg')

    @api.post('/datasets/{dataset_id}/confirm')
    def confirm(dataset_id: str, body: ConfirmRequest, current=Depends(auth), db=Depends(get_db)):
        dataset = owned(db, dataset_id, current[0].id)
        if dataset.status != 'ready' or dataset.version != body.version:
            raise HTTPException(409, 'Dataset changed or is not ready. Refresh.')
        tables = read_tables(settings, dataset_id, dataset.version)
        if body.table_index >= len(tables):
            raise HTTPException(404, 'Table not found.')
        table = tables[body.table_index]
        if body.rows is not None:
            if not table.get('requires_review'):
                raise HTTPException(422, 'Only extracted image cells are editable. Upload a corrected CSV/XLSX instead.')
            if len(body.rows) != len(table['rows']) or any(len(r) != len(table['columns']) for r in body.rows):
                raise HTTPException(422, 'Corrections must preserve table dimensions.')
            if any(isinstance(c, str) and len(c) > 5000 for row in body.rows for c in row):
                raise HTTPException(422, 'A corrected cell is too long.')
            # Reject non-finite JSON numbers before persisting a new table version.
            try:
                json.dumps(body.rows, allow_nan=False)
            except ValueError:
                raise HTTPException(422, 'Cells must contain finite values.') from None
            table['rows'] = body.rows
        table['confirmed'] = True
        new_version = dataset.version + 1
        updated = db.execute(update(Dataset).where(Dataset.id == dataset_id, Dataset.version == body.version).values(version=new_version))
        if not updated.rowcount:
            raise HTTPException(409, 'Dataset changed. Refresh.')
        write_json(version_path(settings, dataset_id, new_version), tables)
        db.commit()
        return {'version': new_version}

    @api.post('/datasets/{dataset_id}/classification')
    def classification(dataset_id: str, body: ClassificationRequest, current=Depends(auth), db=Depends(get_db)):
        dataset = owned(db, dataset_id, current[0].id)
        if body.classification == 'synthetic' and not body.acknowledge:
            raise HTTPException(422, 'Confirm that the dataset and questions contain synthetic information only.')
        # Serialize with job claiming so running requests cannot be reclassified midway.
        db.rollback()
        db.execute(text('BEGIN IMMEDIATE'))
        dataset = owned(db, dataset_id, current[0].id)
        active = db.scalar(select(func.count()).select_from(Job).where(Job.dataset_id == dataset_id, Job.kind == 'question', Job.status == 'running'))
        if active:
            raise HTTPException(409, 'Wait for the current cloud request to finish before changing classification.')
        dataset.classification = body.classification
        if body.classification == 'restricted':
            db.execute(update(Job).where(Job.dataset_id == dataset_id, Job.kind == 'question', Job.status == 'queued').values(status='failed', error='Cloud request cancelled: dataset is Restricted.'))
        db.commit()
        return {'classification': dataset.classification}

    def enqueue(body, kind, user, db):
        dataset, table = table_for(db, body, user)
        payload = body.model_dump()
        if kind == 'question':
            if dataset.classification != 'synthetic':
                raise HTTPException(403, 'Cloud analysis is blocked for Restricted data. Use Local calculation.')
            if not settings.configured:
                raise HTTPException(503, 'Cloud API is not configured. Set OPENAI_API_KEY or use Local calculation.')
        else:
            from .schemas import AnalysisPlan
            from pydantic import ValidationError
            try:
                plan = AnalysisPlan.model_validate(body.plan)
            except ValidationError:
                raise HTTPException(422, 'Invalid calculation instructions.') from None
            payload['plan'] = plan.model_dump(mode='json')
            payload['question'] = f'Local {plan.action}'
        pending = db.scalar(select(func.count()).select_from(Job).where(Job.user_id == user.id, Job.status.in_(['queued', 'running'])))
        if pending >= 5:
            raise HTTPException(429, 'Wait for current jobs to finish before adding more.')
        job = Job(user_id=user.id, dataset_id=dataset.id, kind=kind, payload=json.dumps(payload))
        db.add(job)
        db.commit()
        return {'job_id': job.id}

    @api.post('/questions', status_code=202)
    def question(body: QuestionRequest, current=Depends(auth), db=Depends(get_db)):
        return enqueue(body, 'question', current[0], db)

    @api.post('/analyses', status_code=202)
    def analysis(body: CalculationRequest, current=Depends(auth), db=Depends(get_db)):
        return enqueue(body, 'analysis', current[0], db)

    @api.get('/jobs/{job_id}')
    def job_status(job_id: str, current=Depends(auth), db=Depends(get_db)):
        job = db.get(Job, job_id)
        if not job or job.user_id != current[0].id:
            raise HTTPException(404, 'Job not found.')
        return {'id': job.id, 'status': job.status, 'error': job.error, 'result': json.loads(job.result) if job.result else None}

    @api.post('/jobs/{job_id}/retry', status_code=202)
    def retry(job_id: str, current=Depends(auth), db=Depends(get_db)):
        job = db.get(Job, job_id)
        if not job or job.user_id != current[0].id:
            raise HTTPException(404, 'Job not found.')
        if job.status not in {'failed', 'interrupted'}:
            raise HTTPException(409, 'Only failed or interrupted jobs can be retried.')
        dataset = owned(db, job.dataset_id, current[0].id)
        if job.kind != 'ingest':
            payload = json.loads(job.payload)
            if payload['version'] != dataset.version:
                raise HTTPException(409, 'Dataset changed. Submit a new question.')
            if job.kind == 'question' and dataset.classification != 'synthetic':
                raise HTTPException(403, 'Restricted data cannot be sent to cloud AI.')
        else:
            dataset.status, dataset.error = 'queued', None
        job.status, job.error, job.result, job.finished_at = 'queued', None, None, None
        db.commit()
        return {'job_id': job.id}

    @api.get('/conversations')
    def conversations(dataset_id: str, current=Depends(auth), db=Depends(get_db)):
        owned(db, dataset_id, current[0].id)
        messages = db.scalars(select(Message).where(Message.dataset_id == dataset_id, Message.user_id == current[0].id).order_by(Message.created_at).limit(200)).all()
        return {'messages': [{'id': m.id, 'question': m.question, 'result': json.loads(m.result), 'created_at': m.created_at} for m in messages]}

    @api.delete('/datasets/{dataset_id}')
    def remove(dataset_id: str, current=Depends(auth), db=Depends(get_db)):
        dataset = owned(db, dataset_id, current[0].id)
        db.rollback()
        db.execute(text('BEGIN IMMEDIATE'))
        dataset = owned(db, dataset_id, current[0].id)
        if db.scalar(select(func.count()).select_from(Job).where(Job.dataset_id == dataset_id, Job.status == 'running')):
            raise HTTPException(409, 'Wait for processing to finish before deleting this dataset.')
        directory = dataset_dir(settings, dataset_id)
        # dataset_dir checks containment; never accept a user path for recursive deletion.
        if directory.exists():
            shutil.rmtree(directory)
        db.execute(delete(Message).where(Message.dataset_id == dataset_id))
        db.execute(delete(Job).where(Job.dataset_id == dataset_id))
        db.delete(dataset)
        db.commit()
        return {'ok': True}

    @api.get('/settings')
    def get_settings(current=Depends(auth), db=Depends(get_db)):
        usages = db.scalars(select(Usage).where(Usage.user_id == current[0].id)).all()
        return {'model': settings.model, 'configured': settings.configured, 'ocr_available': bool(tesseract_command()),
                'cloud_enabled': settings.cloud_enabled, 'storage_path': str(settings.data_dir),
                'users_count': db.scalar(select(func.count()).select_from(User)),
                'usage': {'requests': len(usages), 'input_tokens': sum(x.input_tokens for x in usages),
                          'output_tokens': sum(x.output_tokens for x in usages), 'failures': sum(x.failed for x in usages),
                          'latency_ms': sum(x.latency_ms for x in usages)}, 'daily_cloud_limit': settings.daily_cloud_limit}

    app.include_router(api, prefix='/api')
    # Public endpoint aliases preserve the agreed API while UI uses a clear /api namespace.
    app.include_router(api, include_in_schema=False)
    dist = Path(__file__).resolve().parents[2] / 'frontend' / 'dist'
    if dist.is_dir():
        app.mount('/', StaticFiles(directory=dist, html=True), name='frontend')
    else:
        @app.get('/')
        def no_frontend():
            return {'message': 'Build the frontend with npm run build in frontend/, then restart.', 'api': '/api/docs'}
    return app


app = create_app()
