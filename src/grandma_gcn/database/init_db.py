from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import OperationalError
from sqlalchemy import text

from grandma_gcn.gcn_stream.gcn_logging import LoggerNewLine


def init_db(
    database_url: str,
    echo: bool = False,
    logger: LoggerNewLine = None,
) -> tuple[Engine, sessionmaker]:
    """
    Initialise la connexion à la base de données PostgreSQL avec SQLAlchemy.

    Arguments
    ----------
    * `database_url`: str — URL de la base PostgreSQL (ex: postgresql://user:password@localhost/db)
    * `echo`: bool — Affiche les requêtes SQL si True (utile pour debug)

    Return
    ----------
    * `engine`: SQLAlchemy Engine — Moteur de connexion à la base
    * `SessionLocal`: sessionmaker — Classe de session SQLAlchemy
    """
    try:
        engine = create_engine(database_url, echo=echo, future=True)
        SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

        # Vérifie la connexion
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        logger.info("Connexion à la base réussie.")

        return engine, SessionLocal
    except OperationalError as e:
        logger.error("Erreur de connexion à la base :", e, exc_info=1)
        raise
