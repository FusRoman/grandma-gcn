from pathlib import Path
import shutil
from typing import Any
from fink_utils.slack_bot.bot import init_slackbot
from yarl import URL
from astropy.table import Table

from grandma_gcn.gcn_stream.gw_alert import GW_alert
from grandma_gcn.slackbot.gw_message import (
    build_gwemopt_results_message,
    new_alert_on_slack,
    build_gwemopt_message,
    post_image_on_slack,
)
from grandma_gcn.worker.celery_app import celery
import logging
from celery import current_task

from astropy.time import Time

from grandma_gcn.worker.gwemopt_init import GalaxyCatalog, init_gwemopt
from contextlib import redirect_stdout, redirect_stderr

from grandma_gcn.worker.owncloud_client import OwncloudClient


def setup_task_logger(
    task_name: str, log_path: Path, task_id: str
) -> tuple[logging.Logger, Path]:
    """
    Configure a logger to log into a separate file for each task.

    Parameters
    ----------
    task_name : str
        The name of the task.
    log_path : Path
        The path where the log files will be stored.
    task_id : str
        The unique identifier for the task, used to create a unique log file name.

    Returns
    -------
    tuple[logging.Logger, Path]
        A tuple containing the logger and the path to the log file.
    """
    logger = logging.getLogger(f"gcn_stream.consumer.worker.{task_id}")
    logger.setLevel(logging.INFO)

    # Create a file handler for the task
    log_file = log_path / f"{task_name}_{task_id}.log"
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

    return logger, log_file


def run_gwemopt(
    gw_alert: GW_alert,
    telescopes: list[str],
    nb_tiles: list[str],
    nside: int,
    path_output: Path,
    observation_strategy: GW_alert.ObservationStrategy,
    logger: logging.Logger,
    path_galaxy_catalog: Path | None,
    galaxy_catalog: GalaxyCatalog | None,
) -> tuple[Table, Any]:
    """
    Run the gwemopt observation plan.

    Parameters
    ----------
    gw_alert : GW_alert
        The GW_alert object containing the alert information.
    telescopes : list[str]
        List of telescopes to use for the observation plan.
    nside : int
        The nside parameter for the skymap.
    path_output : Path
        Path to the output directory.
    observation_strategy : GW_alert.ObservationStrategy
        The observation strategy to use.
    logger : logging.Logger
        Logger to use for logging. If None, a new logger will be created.
    path_galaxy_catalog : Path | None
        Path to the galaxy catalog directory.
    galaxy_catalog : GalaxyCatalog | None
        The galaxy catalog to use.

    Returns
    -------
    tuple[Table, Any]
        - tiles_tables: the table of tiles generated by gwemopt
        - galaxies_table: the table of galaxies generated by gwemopt
    """
    logger.info("Flattening the skymap...")
    flat_map = gw_alert.flatten_skymap(nside)
    logger.info("Flat map created. Initializing gwemopt...")

    params, map_struct = init_gwemopt(
        flat_map,
        convert_to_nested=False,
        exposure_time=[30 for _ in range(len(nb_tiles))],
        max_nb_tile=nb_tiles,
        nside=nside,
        do_3d=False,
        do_plot=True,
        do_observability=True,
        do_footprint=True,
        do_movie=True,
        moon_check=False,
        do_reference=True,
        path_catalog=path_galaxy_catalog,
        galaxy_catalog=galaxy_catalog,
    )

    logger.info("gwemopt initialized. Running observation plan...")
    obs_plan_results = gw_alert.run_observation_plan(
        telescopes,
        params,
        map_struct,
        str(path_output),
        observation_strategy,
    )
    logger.info("Observation plan completed.")

    return obs_plan_results


def table_to_custom_ascii(telescope: str, table: Table | None) -> str:
    """
    Convert a table returned by gwemopt to a custom ASCII format for the grandma owncloud.

    Parameters
    ----------
    telescope : str
        The name of the telescope.
    table : Table | None
        The table containing the observation plan data. If None, a message indicating no tiles will be returned.

    Returns
    -------
    str
        The formatted string in the custom ASCII format.
    """
    lines = [f"# {telescope}"]
    lines.append("rank_id       tile_id       RA       DEC       Prob   Timeobs")

    if not table:
        lines.append("# No tiles to observe")
        return "\n".join(lines)

    for row in table:
        rank_id = row["rank_id"]
        tile_id = row["tile_id"]
        ra = row["RA"] * 180 / 3.141592653589793  # rad → deg
        dec = row["DEC"] * 180 / 3.141592653589793  # rad → deg
        prob = row["Prob"]
        timeobs = Time(row["Timeobs"]).iso  # format ISO, eg. 2025-05-27 08:49:22.577

        # truncate ms to 3 digits
        timeobs = timeobs[:23]

        # Format the line with fixed spacing
        line = (
            f"{rank_id:<4} {tile_id:<8} {ra:<10.4f} {dec:<10.4f} {prob:<8.4f} {timeobs}"
        )
        lines.append(line)

    return "\n".join(lines)


def push_gwemopt_product_on_owncloud(
    owncloud_client: OwncloudClient,
    path_gwemopt: Path,
    owncloud_url: URL,
    pattern: str = "*.png",
):
    """
    Push the gwemopt product to ownCloud.

    Parameters
    ----------
    owncloud_client : OwncloudClient
        The ownCloud client to use for uploading files.
    path_gwemopt : Path
        The local path where the gwemopt product is stored.
    owncloud_url : URL
        The URL of the ownCloud instance where the product will be uploaded.
    pattern : str
        The pattern to match files to upload. Default is "*.png".
    """
    list_plot_path = path_gwemopt.glob(pattern)
    for f in list_plot_path:
        owncloud_filename = f.name
        owncloud_client.put_file(f, owncloud_url, owncloud_filename)
        owncloud_client.logger.info(
            f"File {owncloud_filename} successfully uploaded to {owncloud_url}"
        )
    owncloud_client.logger.info(
        f"All gwemopt products successfully uploaded to {owncloud_url}"
    )


@celery.task(name="gwemopt_task")
def gwemopt_task(
    telescopes: list[str],
    nb_tiles: list[int],
    nside: int,
    slack_channel: str,
    channel_id: str,
    owncloud_config: dict[str, Any],
    owncloud_gwemopt_url: str,
    path_gw_alert: str,
    path_notice: str,
    path_output: str,
    path_log: str,
    BBH_threshold: float,
    Distance_threshold: float,
    ErrorRegion_threshold: float,
    obs_strategy: str,
    path_galaxy_catalog: str | None = None,
    galaxy_catalog: str | None = None,
) -> None:
    """
    Task to process the GCN notice.

    Parameters
    ----------
    telescopes : listpath_log[str]
        List of telescopes to use for the observation plan.
    nb_tiles : list[int]
        Number of tiles for each telescope.
    nside : int
        The nside parameter for the skymap.
    slack_channel : str
        The Slack channel to send the notification to.
    channel_id : str
        The Slack channel ID to send the notification to.
        Different from slack_channel, this is the ID used by the Slack API.
    owncloud_gwemopt_url : str
        The URL for the ownCloud instance where the results will be stored.
    path_gw_alert : str
        Path to the gw alert folder on OWNCLOUD.
    path_output : str
        Path to the output directory.
    path_notice : str
        Path to the GCN notice file.
    BBH_threshold : float
        Threshold for BBH probability.
    Distance_threshold : float
        Threshold for distance cut.
    ErrorRegion_threshold : float
        Threshold for size region cut.
    path_galaxy_catalog : str
        Path to the galaxy catalog directory.
    galaxy_catalog : str
        The galaxy catalog to use.
    """

    # Initialize the ownCloud client and URL
    owncloud_client = OwncloudClient(owncloud_config)
    owncloud_gwemopt_url = URL(owncloud_gwemopt_url)

    obs_strategy: GW_alert.ObservationStrategy = (
        GW_alert.ObservationStrategy.from_string(obs_strategy)
    )
    if obs_strategy == GW_alert.ObservationStrategy.GALAXYTARGETING and (
        path_galaxy_catalog is None or galaxy_catalog is None
    ):
        raise ValueError(
            "Observation strategy is set to GALAXYTARGETING but no galaxy catalog path or galaxy catalog provided."
        )

    alert_url_subpart = owncloud_client.get_url_subpart(owncloud_gwemopt_url, 5)
    obs_strategy_owncloud_path = (
        alert_url_subpart + f"/{obs_strategy.name}_{"_".join(telescopes)}"
    )
    # create specific observation strategy owncloud folder
    obs_strategy_owncloud_url_folder = owncloud_client.mkdir(obs_strategy_owncloud_path)

    start_task = Time.now()
    task_id = current_task.request.id
    path_notice = Path(path_notice)
    output_path = Path(path_output)
    path_galaxy_catalog = Path(path_galaxy_catalog) if path_galaxy_catalog else None
    galaxy_catalog = (
        GalaxyCatalog.from_string(galaxy_catalog) if galaxy_catalog else None
    )

    try:
        with open(path_notice, "rb") as fp:
            json_byte = fp.read()

        gw_alert = GW_alert(
            json_byte,
            BBH_threshold=BBH_threshold,
            Distance_threshold=Distance_threshold,
            ErrorRegion_threshold=ErrorRegion_threshold,
        )  # Configure a logger specific to this task

        logger, log_file_path = setup_task_logger(
            "gwemopt_task_{}".format(gw_alert.event_id), Path(path_log), task_id
        )

        with open(log_file_path, "a") as log_file:
            with redirect_stdout(log_file), redirect_stderr(log_file):
                logger.info("Starting gwemopt_task...")

                worker_slack_client = init_slackbot(logger)

                # Send a message to Slack to inform that a gwemopt task is starting
                new_alert_on_slack(
                    gw_alert,
                    build_gwemopt_message,
                    worker_slack_client,
                    channel=slack_channel,
                    logger=logger,
                    obs_strategy=obs_strategy,
                    celery_task_id=task_id,
                    task_start_time=start_task,
                    telescopes=telescopes,
                )

                tiles, _ = run_gwemopt(
                    gw_alert,
                    telescopes,
                    nb_tiles,
                    nside=nside,
                    path_output=output_path,
                    observation_strategy=obs_strategy,
                    logger=logger,
                    path_galaxy_catalog=path_galaxy_catalog,
                    galaxy_catalog=galaxy_catalog,
                )

                # create the owncloud folder for the gwemopt plots and data files
                logger.info("Pushing gwemopt products to ownCloud...")
                plots_owncloud_url_folder = owncloud_client.mkdir(
                    obs_strategy_owncloud_path + "/plots"
                )
                push_gwemopt_product_on_owncloud(
                    owncloud_client,
                    output_path,
                    plots_owncloud_url_folder,
                    pattern="*.png",
                )

                logger.info("Successfully pushed plots to ownCloud.")

                push_gwemopt_product_on_owncloud(
                    owncloud_client,
                    output_path,
                    plots_owncloud_url_folder,
                    pattern="*.dat",
                )

                logger.info("Successfully pushed data files to ownCloud.")

                # Upload the tiles table in custom ASCII format to ownCloud
                for k, v in tiles.items():
                    gwemopt_ascii_tiles = table_to_custom_ascii(k, v)
                    owncloud_client.put_data(
                        data=gwemopt_ascii_tiles.encode("utf-8"),
                        url=obs_strategy_owncloud_url_folder,
                        owncloud_filename=f"tiles_{k}.txt",
                    )

                logger.info(
                    "Tiles table converted to custom ASCII format and uploaded to ownCloud."
                )

                logger.info("GW_alert successfully processed.")

                # Post the gwemopt result message on Slack
                gwemopt_result_response = new_alert_on_slack(
                    gw_alert,
                    build_gwemopt_results_message,
                    worker_slack_client,
                    channel=slack_channel,
                    logger=logger,
                    tiles_plan=tiles,
                    celery_task_id=task_id,
                    execution_time=(Time.now() - start_task).sec,
                    obs_strategy=obs_strategy,
                    telescopes=telescopes,
                    path_gw_alert=path_gw_alert,
                )

                logger.info("gwemopt post message successfully sent to Slack.")

                try:
                    # Post the coverage map on Slack
                    post_image_on_slack(
                        worker_slack_client,
                        filepath=output_path / "tiles_coverage_int.png",
                        filetitle=f"{gw_alert.event_id} {obs_strategy.value} {"_".join(telescopes)} Coverage Map",
                        filename=f"coverage_{gw_alert.event_id}_{obs_strategy.value}_map.png",
                        channel_id=channel_id,
                        threads_ts=gwemopt_result_response["ts"],
                    )
                except FileNotFoundError as e:
                    logger.error(
                        f"Coverage map file not found: {e}. Skipping posting map on Slack."
                    )

                logger.info("Coverage map posted on slack in the message thread")

    except Exception as e:
        logger.error(f"An error occurred while processing the task: {e}")
        raise e

    return str(path_notice), str(output_path)


@celery.task(name="gwemopt_post_task")
def gwemopt_post_task(results):
    """
    Task to clean up after the gwemopt task has completed.
    This task removes the notice file and the output directory created by the gwemopt task.

    Parameters
    ----------
    results : tuple[str, str]
        A tuple containing the path to the notice file and the path to the output directory.
    """

    path_notice = Path(results[0][0])
    # remove the notice file after processing
    path_notice.unlink()

    for _, path_gwemopt_output in results:
        folder_gwemopt_output = Path(path_gwemopt_output)
        # remove the output directory after processing
        if folder_gwemopt_output.exists() and folder_gwemopt_output.is_dir():
            shutil.rmtree(folder_gwemopt_output)
