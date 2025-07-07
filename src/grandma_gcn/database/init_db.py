from sqlalchemy import Engine, create_engine, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker

from grandma_gcn.gcn_stream.gcn_logging import LoggerNewLine


def init_db(
    database_url: str,
    echo: bool = False,
    logger: LoggerNewLine = None,
) -> tuple[Engine, sessionmaker[Session]]:
    """
    Initialize the database connection and return the SQLAlchemy engine and session factory.

    Parameters
    ----------
    database_url : str
        PostgreSQL database URL (e.g., postgresql://user:password@localhost/db)
    echo : bool, optional
        If True, SQL statements will be logged to the console (useful for debugging). Default is False.
    logger : LoggerNewLine, optional
        Logger instance for logging connection status and errors. If None, no logging is performed.

    Returns
    -------
    engine : sqlalchemy.Engine
        SQLAlchemy engine instance connected to the database.
    SessionLocal : sessionmaker[Session]
        SQLAlchemy session factory for creating new sessions.

    Raises
    ------
    sqlalchemy.exc.OperationalError
        If the connection to the database fails.
    """
    try:
        engine = create_engine(database_url, echo=echo, future=True)
        SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        logger.info("Connection to the database successful.")

        return engine, SessionLocal
    except OperationalError as e:
        logger.error("Error raised during the database connection :", e, exc_info=1)
        raise
