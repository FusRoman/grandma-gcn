from functools import wraps
from os import environ
from pathlib import Path

from celery import Celery
from celery.utils.log import get_task_logger
from dotenv import dotenv_values
from sqlalchemy.exc import SQLAlchemyError

from grandma_gcn.database.session import get_session_local


def initialize_celery(env_file: Path) -> Celery:
    """
    Initialize a Celery application with the given configuration or from a .env file.

    Parameters
    ----------
    env_file : str, optional
        The path to the .env file to load configuration from. Defaults to ".env".

    Returns
    -------
    Celery
        The initialized Celery application.
    """
    env_vars = dotenv_values(env_file)

    config_dict = {
        "broker_url": env_vars.get("CELERY_BROKER_URL", "redis://localhost:6379/0"),
        "result_backend": env_vars.get(
            "CELERY_RESULT_BACKEND", "redis://localhost:6379/0"
        ),
        "timezone": env_vars.get("TIMEZONE", "UTC"),
    }

    app = Celery(
        "grandma_gcn",
        broker=config_dict["broker_url"],
        backend=config_dict["result_backend"],
    )

    app.conf.update(
        task_serializer="json",
        accept_content=["json"],
        result_serializer="json",
        timezone=config_dict["timezone"],
        enable_utc=True,
    )

    return app


def with_session(fn):
    """
    Decorator that injects a SQLAlchemy session into a function and
    ensures it is properly committed or rolled back and closed.

    The session is automatically committed if no exceptions occur.
    Otherwise, it is rolled back.

    The function being decorated must accept the session as its first argument.
    """

    @wraps(fn)
    def wrapper(*args, **kwargs):
        SessionLocal = get_session_local()
        session = SessionLocal()
        try:
            with session.begin():
                return fn(session, *args, **kwargs)
        except SQLAlchemyError as e:
            session.rollback()  # rollback in case of error outside the context block
            raise e
        finally:
            session.close()

    return wrapper


name_env_file = ".env"
env_file_variable = "NAME_ENV_FILE"
logger = get_task_logger(__file__)
logger.debug(environ)
if env_file_variable in environ:
    name_env_file = environ.get(env_file_variable)
    logger.warning(
        f"{env_file_variable} environment variable detected\ninitialise flask app using the environment file named {name_env_file}"
    )

celery = initialize_celery(Path(name_env_file))
