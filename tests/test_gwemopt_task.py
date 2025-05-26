import tempfile
import logging
from grandma_gcn.gcn_stream.gw_alert import GW_alert
from grandma_gcn.gcn_stream.stream import load_gcn_config
from grandma_gcn.worker.gwemopt_init import init_gwemopt
import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path

from grandma_gcn.worker.gwemopt_worker import gwemopt_task
from tests.test_gw_alert import open_notice_file
from grandma_gcn.worker.celery_app import celery


@pytest.fixture(autouse=True)
def celery_eager():
    celery.conf.update(task_always_eager=True)


def test_init_gwemopt_basic(gw_alert_unsignificant: GW_alert):
    nside = 16
    flat_map = gw_alert_unsignificant.flatten_skymap(nside)

    params, map_struct = init_gwemopt(
        flat_map,
        False,
        exposure_time=[100],
        max_nb_tile=[10],
        nside=nside,
        do_3d=False,
        do_plot=False,
        do_observability=False,
        do_footprint=False,
        do_movie=False,
        moon_check=False,
        do_reference=True,
    )

    # Vérification des paramètres (inchangé)
    assert isinstance(params, dict)
    assert params["exposuretimes"] == [100]
    assert params["max_nb_tiles"] == [10]
    assert params["nside"] == nside
    assert params["do3D"] is False
    assert params["doPlots"] is False
    assert params["doObservability"] is False
    assert params["doFootprint"] is False
    assert params["doMovie"] is False
    assert params["Moon_check"] is False
    assert params["doReferences"] is True

    # Vérification détaillée de la structure de la carte
    assert isinstance(map_struct, dict)
    # Champs obligatoires
    for key in [
        "prob",
        "ra",
        "dec",
        "cumprob",
        "ipix_keep",
        "nside",
        "npix",
        "pixarea",
        "pixarea_deg2",
    ]:
        assert key in map_struct, f"Clé manquante dans map_struct: {key}"

    # Types et cohérence des shapes
    assert hasattr(map_struct["prob"], "shape")
    assert map_struct["prob"].ndim == 1
    assert map_struct["ra"].shape == map_struct["dec"].shape == map_struct["prob"].shape

    # Validité des valeurs
    assert (map_struct["prob"] >= 0).all()
    assert map_struct["prob"].sum() > 0
    assert map_struct["nside"] == nside
    assert map_struct["npix"] == len(map_struct["prob"])
    assert map_struct["pixarea_deg2"] > 0

    # Vérification des champs optionnels si présents (3D)
    for key in ["distmu", "distsigma", "distnorm"]:
        assert map_struct[key] is None


def test_init_gwemopt_S241102_update(S241102_update: GW_alert):
    nside = 16
    flat_map = S241102_update.flatten_skymap(nside)

    params, map_struct = init_gwemopt(
        flat_map,
        False,
        exposure_time=[100],
        max_nb_tile=[10],
        nside=nside,
        do_3d=False,
        do_plot=False,
        do_observability=False,
        do_footprint=False,
        do_movie=False,
        moon_check=False,
        do_reference=True,
    )

    # Vérification des paramètres
    assert isinstance(params, dict)
    assert params["exposuretimes"] == [100]
    assert params["max_nb_tiles"] == [10]
    assert params["nside"] == nside
    assert params["do3D"] is False
    assert params["doPlots"] is False
    assert params["doObservability"] is False
    assert params["doFootprint"] is False
    assert params["doMovie"] is False
    assert params["Moon_check"] is False
    assert params["doReferences"] is True

    # Vérification détaillée de la structure de la carte
    assert isinstance(map_struct, dict)
    for key in [
        "prob",
        "ra",
        "dec",
        "cumprob",
        "ipix_keep",
        "nside",
        "npix",
        "pixarea",
        "pixarea_deg2",
    ]:
        assert key in map_struct, f"Clé manquante dans map_struct: {key}"

    # Types et cohérence des shapes
    assert hasattr(map_struct["prob"], "shape")
    assert map_struct["prob"].ndim == 1
    assert map_struct["ra"].shape == map_struct["dec"].shape == map_struct["prob"].shape

    # Validité des valeurs
    assert (map_struct["prob"] >= 0).all()
    assert map_struct["prob"].sum() > 0
    assert map_struct["nside"] == nside
    assert map_struct["npix"] == len(map_struct["prob"])
    assert map_struct["pixarea_deg2"] > 0

    # Vérification des champs optionnels si présents (3D)
    for key in ["distmu", "distsigma", "distnorm"]:
        assert map_struct[key].shape == map_struct["prob"].shape


@pytest.mark.usefixtures("tmp_path")
def test_gwemopt_task_celery(tmp_path, S241102_update):

    # Create a temporary directory for saving notices
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        notice_path = S241102_update.save_notice(temp_path)

        # Préparation des paramètres
        telescopes = ["TCH", "TRE"]
        nb_tiles = [10, 10]
        nside = 16
        path_output = tmp_path / "output"
        BBH_threshold = 0.5
        Distance_threshold = 500
        ErrorRegion_threshold = 500

        # Patch Observation_plan_multiple pour éviter le calcul lourd
        with patch(
            "grandma_gcn.gcn_stream.gw_alert.Observation_plan_multiple"
        ) as mock_obs_plan:
            mock_obs_plan.return_value = (MagicMock(), MagicMock())

            # Patch logger pour éviter la création de fichiers log
            with patch(
                "grandma_gcn.worker.gwemopt_worker.setup_task_logger"
            ) as mock_logger:
                mock_logger.return_value = logging.getLogger()

                # Exécution synchrone de la tâche celery
                gwemopt_task.apply(
                    args=[
                        telescopes,
                        nb_tiles,
                        nside,
                        "#test_channel",
                        str(notice_path),
                        str(path_output),
                        BBH_threshold,
                        Distance_threshold,
                        ErrorRegion_threshold,
                        GW_alert.ObservationStrategy.TILING.name,
                    ]
                )

            assert mock_obs_plan.called


def test_process_alert_calls(mocker):
    """
    Teste que process_alert crée bien un GW_alert et retourne un message selon le score.
    """
    from grandma_gcn.gcn_stream.consumer import Consumer

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        # Mock gcn_stream et sa config
        mock_gcn_stream = MagicMock()
        mock_gcn_stream.gcn_config = load_gcn_config(
            Path("tests", "gcn_stream_test.toml"), logger=logging.getLogger()
        )
        mock_gcn_stream.notice_path = temp_path

        notice = open_notice_file(Path("tests"), "S241102br-update.json")

        mock_post_msg_on_slack = mocker.patch(
            "grandma_gcn.slackbot.gw_message.post_msg_on_slack"
        )

        # Patch Observation_plan_multiple pour éviter le calcul lourd
        with patch(
            "grandma_gcn.gcn_stream.gw_alert.Observation_plan_multiple"
        ) as mock_obs_plan:
            mock_obs_plan.return_value = (MagicMock(), MagicMock())

            consumer = Consumer(gcn_stream=mock_gcn_stream)
            consumer.process_alert(notice)

            assert mock_obs_plan.call_count == 2

            assert mock_post_msg_on_slack.call_count == 3
