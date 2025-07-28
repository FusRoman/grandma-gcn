from pathlib import Path

from dotenv import dotenv_values
from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from grandma_gcn.database.init_db import init_db
from grandma_gcn.gcn_stream.gcn_logging import LoggerNewLine

# Internal variables to hold the engine and session factory
_engine = None
_SessionLocal = None


def get_session_local(env_path: Path = Path(".env")) -> sessionmaker[Session]:
    """
    Lazily initialize and return the SQLAlchemy session factory.

    Parameters
    ----------
    env_path : Path
        Path to the .env file containing database credentials.

    Returns
    -------
    sessionmaker
        A configured SQLAlchemy session factory.
    """
    global _engine, _SessionLocal
    if _SessionLocal is None:
        env = dotenv_values(env_path)
        logger = LoggerNewLine(name="sqlalchemy")
        db_url = env["SQLALCHEMY_DATABASE_URI"]
        _engine, _SessionLocal = init_db(db_url, logger=logger)
    return _SessionLocal


def get_engine() -> Engine:
    """
    Return the SQLAlchemy engine instance, initializing it if necessary.

    Returns
    -------
    Engine
        SQLAlchemy engine connected to the database.
    """
    get_session_local()  # ensure engine is initialized
    return _engine
