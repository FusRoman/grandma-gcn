import uuid
from typing import Any

from celery import chord
from sqlalchemy.orm import Session

from grandma_gcn.database.gw_db import GW_alert as GW_alert_DB
from grandma_gcn.gcn_stream.gcn_logging import LoggerNewLine
from grandma_gcn.worker.gwemopt_worker import gwemopt_post_task, gwemopt_task


def automatic_gwemopt_process(
    gcn_stream_config: dict[str, Any],
    gw_alert_db: GW_alert_DB,
    db_session: Session,
    threshold_config: dict[str, float | int],
    gw_alert_channel: str,
    gw_channel_id: str,
    logger: LoggerNewLine,
) -> None:
    """
    Orchestrates the automatic processing of a significant gravitational wave alert by submitting observation plan tasks to the GWEMOPT celery worker.

    The actual generation of observation plans is performed by the celery worker. This function:
        - Marks the alert as being processed in the database to prevent duplicate processing.
        - Prepares observation tasks for each telescope configuration as defined in the configuration.
        - Submits these tasks as a Celery chord, so that a post-processing task is triggered after all observation plans are generated.

    Parameters
    ----------
    gcn_stream_config : dict
        Configuration dictionary for the GCN stream, including GWEMOPT and OWNCLOUD settings.
    gw_alert_db : GW_alert_DB
        Database object representing the gravitational wave alert to process.
    db_session : Session
        SQLAlchemy session for database operations.
    threshold_config : dict
        Dictionary of threshold values for filtering or scoring.
    gw_alert_channel : str
        Slack channel name where the alert was posted.
    gw_channel_id : str
        Slack channel ID.
    logger : LoggerNewLine
        Logger instance for logging progress and status.

    Returns
    -------
    None
        This function does not return anything. It triggers Celery tasks for observation plan generation and post-processing.
    """
    logger.info(
        f"Processing significant alert {gw_alert_db.triggerId} with score > 1, Observation plan will be generated."
    )

    logger.info("Sending gwemopt task to celery worker")

    telescopes_list = gcn_stream_config["GWEMOPT"]["telescopes"]
    number_of_tiles = gcn_stream_config["GWEMOPT"]["number_of_tiles"]
    observation_strategy = gcn_stream_config["GWEMOPT"]["observation_strategy"]

    # Indicate that the alert is being processed
    # This is used to prevent multiple processes from running the same alert
    gw_alert_db.is_process_running = True
    db_session.commit()

    logger.info(
        f"Alert {gw_alert_db.triggerId} is being processed, setting is_process_running to True"
    )
    # construct a list of tasks for each sublist of telescopes, number of tiles and observation strategy
    gwemopt_tasks = [
        gwemopt_task.s(
            tel_list,
            nb_tiles_list,
            gcn_stream_config["GWEMOPT"]["nside_flat"],
            gw_alert_channel,
            gw_channel_id,
            gcn_stream_config["OWNCLOUD"],
            gw_alert_db.id_gw,
            "_".join(
                [
                    gw_alert_db.triggerId,
                    obs_strat,
                    "_".join(tel_list),
                    uuid.uuid4().hex,
                ]
            ),
            gcn_stream_config["PATH"]["celery_task_log_path"],
            threshold_config,
            obs_strat,
            gw_alert_db.thread_ts,
            gcn_stream_config["GWEMOPT"]["path_galaxy_catalog"],
            gcn_stream_config["GWEMOPT"]["galaxy_catalog"],
        )
        for tel_list, nb_tiles_list, obs_strat in zip(
            telescopes_list,
            number_of_tiles,
            observation_strategy,
        )
    ]

    chord(gwemopt_tasks)(
        gwemopt_post_task.s(
            owncloud_config=gcn_stream_config["OWNCLOUD"],
            path_log=gcn_stream_config["PATH"]["celery_task_log_path"],
        )
    )
