"""Create SQLAlchemy database Sessions."""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from config import DATABASE_ARGS, SQLALCHEMY_DATABASE_URI

engine = create_engine(
    SQLALCHEMY_DATABASE_URI,
    connect_args=DATABASE_ARGS,
    echo=False,
    pool_pre_ping=True,  # Discard stale connections before use
    pool_recycle=3600,  # Recycle connections every hour (< MySQL wait_timeout)
)
Session = sessionmaker(bind=engine, autoflush=True, autobegin=True)
