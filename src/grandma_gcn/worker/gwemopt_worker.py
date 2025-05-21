from pathlib import Path
import time
import uuid

from grandma_gcn.gcn_stream.gw_alert import GW_alert
from grandma_gcn.worker.celery_app import celery
import logging


def setup_task_logger(task_name: str) -> logging.Logger:
    """
    Configure a logger to log into a separate file for each task.

    Parameters
    ----------
    task_name : str
        The name of the task.

    Returns
    -------
    logging.Logger
        The configured logger.
    """
    id_task = uuid.uuid4()
    logger = logging.getLogger(f"gcn_stream.consumer.worker.{id_task}")
    logger.setLevel(logging.INFO)

    # Create a file handler for the task
    log_file = Path(f"task_logs/{task_name}_{id_task}.log")
    log_file.parent.mkdir(
        parents=True, exist_ok=True
    )  # Create the logs directory if it doesn't exist
    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(logging.INFO)

    # Create a formatter and add it to the handler
    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    file_handler.setFormatter(formatter)

    # Add the handler to the logger
    if not logger.handlers:  # Avoid adding multiple handlers
        logger.addHandler(file_handler)

    return logger


@celery.task(name="gwemopt_task")
def gwemopt_task(
    path_notice: str,
    BBH_threshold: float,
    Distance_threshold: float,
    ErrorRegion_threshold: float,
) -> None:
    """
    Task to process the GCN notice.

    Parameters
    ----------
    path_notice : str
        Path to the GCN notice file.
    BBH_threshold : float
        Threshold for BBH probability.
    Distance_threshold : float
        Threshold for distance cut.
    ErrorRegion_threshold : float
        Threshold for size region cut.
    """
    path_notice = Path(path_notice)
    try:
        with open(path_notice, "rb") as fp:
            json_byte = fp.read()

        gw_alert = GW_alert(
            json_byte,
            BBH_threshold=BBH_threshold,
            Distance_threshold=Distance_threshold,
            ErrorRegion_threshold=ErrorRegion_threshold,
        )  # Configure a logger specific to this task
        logger = setup_task_logger("gwemopt_task_{}".format(gw_alert.event_id))
        logger.info("Starting gwemopt_task...")
        time.sleep(10)  # Simulate some processing time
        logger.info("GW_alert successfully processed.")
    except Exception as e:
        logger.error(f"An error occurred while processing the task: {e}")
        raise


def main():
    # Chemin vers une notice de test
    test_notice_path = Path("tests/notice_examples/S241102br-initial.json")

    # Vérifiez que le fichier existe
    if not test_notice_path.exists():
        print(f"Le fichier de test {test_notice_path} n'existe pas.")
        return

    # Paramètres pour la tâche
    BBH_threshold = 0.5
    Distance_threshold = 500.0
    ErrorRegion_threshold = 100.0

    # Lancer la tâche Celery
    print("Lancement de la tâche Celery...")
    task = gwemopt_task.delay(
        str(test_notice_path),
        BBH_threshold,
        Distance_threshold,
        ErrorRegion_threshold,
    )

    # Afficher l'ID de la tâche
    print(f"Tâche lancée avec succès. ID de la tâche : {task.id}")


if __name__ == "__main__":
    main()
