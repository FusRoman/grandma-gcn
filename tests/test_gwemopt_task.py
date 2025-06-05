import pickle
import tempfile
import logging

from yarl import URL
from grandma_gcn.gcn_stream.gw_alert import GW_alert
from grandma_gcn.gcn_stream.stream import load_gcn_config
from grandma_gcn.worker.gwemopt_init import GalaxyCatalog, init_gwemopt
import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path

from grandma_gcn.worker.gwemopt_worker import gwemopt_task
from tests.test_gw_alert import open_notice_file
from grandma_gcn.worker.celery_app import celery
from grandma_gcn.worker.owncloud_client import OwncloudClient


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
        path_catalog=None,
        galaxy_catalog=None,
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
        assert key in map_struct, f"Missing key in map_struct: {key}"

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
        path_catalog=Path("catalogs"),
        galaxy_catalog=GalaxyCatalog.MANGROVE,
    )

    assert params["catalogDir"] == "catalogs"
    assert params["galaxy_catalog"] == "mangrove"


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
        path_catalog=None,
        galaxy_catalog=None,
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
def test_gwemopt_task_celery(mocker, tmp_path, S241102_update):

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

        mock_owncloud_mkdir_request = mocker.patch("requests.request")
        mock_owncloud_mkdir_request.return_value.status_code = 201

        # Patch Observation_plan_multiple pour éviter le calcul lourd
        with patch(
            "grandma_gcn.gcn_stream.gw_alert.Observation_plan_multiple"
        ) as mock_obs_plan:
            mock_obs_plan.return_value = (MagicMock(), MagicMock())

            # Patch logger pour éviter la création de fichiers log
            with patch(
                "grandma_gcn.worker.gwemopt_worker.setup_task_logger"
            ) as mock_logger:
                mock_logger.return_value = (logging.getLogger(), Path("fake_path_log"))

                # Exécution synchrone de la tâche celery
                gwemopt_task.apply(
                    args=[
                        telescopes,
                        nb_tiles,
                        nside,
                        "#test_channel",
                        "CHANNELID",
                        {
                            "username": "test_user",
                            "password": "test_pass",
                            "base_url": "https://owncloud.example.com",
                        },
                        "https://owncloud.example.com/S241102br/GWEMOPT/UPDATE_fixeduuidhex",
                        "Candidates/GW/S241102br/",
                        str(notice_path),
                        str(path_output),
                        str(tmp_path),
                        BBH_threshold,
                        Distance_threshold,
                        ErrorRegion_threshold,
                        GW_alert.ObservationStrategy.TILING.value,
                    ]
                )

            assert mock_obs_plan.called


def test_process_alert_calls(mocker):
    from grandma_gcn.gcn_stream.consumer import Consumer

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        mock_gcn_stream = MagicMock()
        mock_gcn_stream.gcn_config = load_gcn_config(
            Path("tests", "gcn_stream_test.toml"), logger=logging.getLogger()
        )
        mock_gcn_stream.notice_path = temp_path

        notice = open_notice_file(Path("tests"), "S241102br-update.json")

        mock_post_msg_on_slack = mocker.patch(
            "grandma_gcn.slackbot.gw_message.post_msg_on_slack"
        )

        mock_owncloud_mkdir_request = mocker.patch("requests.request")
        mock_owncloud_mkdir_request.return_value.status_code = 201

        mock_owncloud_put_file = mocker.patch("requests.put")
        mock_owncloud_put_file.return_value.status_code = 201

        # Patch uuid.uuid4 to return an object with a fixed hex value
        class DummyUUID:
            hex = "fixeduuidhex"

        with patch("uuid.uuid4", return_value=DummyUUID()):
            with patch(
                "grandma_gcn.gcn_stream.gw_alert.Observation_plan_multiple"
            ) as mock_obs_plan:
                with patch(
                    "grandma_gcn.slackbot.gw_message.open", create=True
                ) as mock_open:
                    with patch("slack_sdk.WebClient.files_upload_v2") as mock_upload:
                        mock_upload.return_value = {
                            "file": {"permalink_public": "https://fake_url"}
                        }

                        mock_open.return_value.__enter__.return_value = MagicMock()

                        tiles = pickle.load(open("tests/data/tiles.pickle", "rb"))
                        tiles["KAO"] = None  # Simulate no data for KAO
                        tiles["Colibri"] = None  # Simulate no data for Colibri
                        tiles["UBAI-T60S"] = None  # Simulate no data for TCH
                        mock_obs_plan.return_value = (tiles, MagicMock())

                        # Patch OwncloudClient.mkdir to track calls
                        with patch.object(
                            OwncloudClient,
                            "mkdir",
                            autospec=True,
                            wraps=OwncloudClient.mkdir,
                        ) as spy_mkdir:
                            consumer = Consumer(
                                gcn_stream=mock_gcn_stream, logger=logging.getLogger()
                            )
                            consumer.process_alert(notice)

                            # Check that the mkdir calls were made correctly
                            mkdir_args = [
                                call.args[1] for call in spy_mkdir.call_args_list
                            ]
                            assert (
                                "Candidates/GW/S241102br/GWEMOPT/UPDATE_fixeduuidhex/TILING_TCH_TRE"
                                == mkdir_args[7]
                            )

        assert mock_obs_plan.call_count == 4
        assert mock_post_msg_on_slack.call_count == 9
        assert mock_open.call_count == 4
        assert mock_upload.call_count == 4
        assert "tiles_coverage_int.png" in str(mock_open.call_args_list[0][0])
        assert (
            mock_upload.call_args_list[0][1]["filename"]
            == "coverage_S241102br_Tiling_map.png"
        )

        mock_owncloud_mkdir_request.call_count == 11
        _, kwargs = mock_owncloud_mkdir_request.call_args

        assert kwargs["method"] == "MKCOL"
        assert kwargs["url"] == URL(
            "https://owncloud.example.com/Candidates/GW/S241102br/GWEMOPT/UPDATE_fixeduuidhex/GALAXYTARGETING_KAO_Colibri/plots"
        )
