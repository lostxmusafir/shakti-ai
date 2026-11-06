from datetime import datetime, timezone
import uuid

from sqlalchemy import create_engine, event, String, Text, Integer, ForeignKey
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker


def now():
    return datetime.now(timezone.utc).isoformat()


def uid():
    return uuid.uuid4().hex


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = 'users'
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    username: Mapped[str] = mapped_column(String, unique=True)
    password_hash: Mapped[str] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(String, default=now)


class LoginSession(Base):
    __tablename__ = 'sessions'
    token_hash: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'))
    csrf: Mapped[str] = mapped_column(String)
    expires_at: Mapped[str] = mapped_column(String)


class Dataset(Base):
    __tablename__ = 'datasets'
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'), index=True)
    name: Mapped[str] = mapped_column(String)
    classification: Mapped[str] = mapped_column(String, default='restricted')
    status: Mapped[str] = mapped_column(String, default='queued')
    version: Mapped[int] = mapped_column(Integer, default=0)
    table_count: Mapped[int] = mapped_column(Integer, default=0)
    original_path: Mapped[str] = mapped_column(Text)
    sha256: Mapped[str] = mapped_column(String)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    job_id: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[str] = mapped_column(String, default=now)


class Job(Base):
    __tablename__ = 'jobs'
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'), index=True)
    dataset_id: Mapped[str] = mapped_column(ForeignKey('datasets.id'), index=True)
    kind: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, default='queued')
    payload: Mapped[str] = mapped_column(Text, default='{}')
    result: Mapped[str | None] = mapped_column(Text, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[str] = mapped_column(String, default=now)
    finished_at: Mapped[str | None] = mapped_column(String, nullable=True)


class Message(Base):
    __tablename__ = 'messages'
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'), index=True)
    dataset_id: Mapped[str] = mapped_column(ForeignKey('datasets.id'), index=True)
    job_id: Mapped[str] = mapped_column(ForeignKey('jobs.id'), unique=True)
    question: Mapped[str] = mapped_column(Text)
    result: Mapped[str] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(String, default=now)


class Usage(Base):
    __tablename__ = 'usage'
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'), index=True)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    failed: Mapped[int] = mapped_column(Integer, default=0)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[str] = mapped_column(String, default=now)


def connect(settings):
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    engine = create_engine(settings.db_url, connect_args={'check_same_thread': False, 'timeout': 15})

    @event.listens_for(engine, 'connect')
    def pragmas(connection, _):
        cur = connection.cursor()
        cur.execute('PRAGMA journal_mode=WAL')
        cur.execute('PRAGMA foreign_keys=ON')
        cur.execute('PRAGMA busy_timeout=15000')
        cur.close()

    Base.metadata.create_all(engine)
    return engine, sessionmaker(engine, expire_on_commit=False)
