import logging
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from astropy.table import Table
from yarl import URL

from grandma_gcn.gcn_stream.gw_alert import GW_alert
from grandma_gcn.gcn_stream.stream import load_gcn_config
from grandma_gcn.worker.celery_app import celery
from grandma_gcn.worker.gwemopt_init import GalaxyCatalog, init_gwemopt
from grandma_gcn.worker.gwemopt_worker import gwemopt_task
from grandma_gcn.worker.owncloud_client import OwncloudClient
from tests.conftest import open_notice_file


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


def test_gwemopt_task_celery(
    mocker, S241102_update, sqlite_engine_and_session, tiles: dict[str, Table]
):
    with tempfile.TemporaryDirectory() as tmp_path:
        tmp_path = Path(tmp_path)
        telescopes = ["TCH", "TRE"]
        nb_tiles = [10, 10]
        nside = 16
        path_output = tmp_path / "output"
        path_output.mkdir(parents=True, exist_ok=True)
        BBH_threshold = 0.5
        Distance_threshold = 500
        ErrorRegion_threshold = 500

        mock_owncloud_mkdir_request = mocker.patch("requests.request")
        mock_owncloud_mkdir_request.return_value.status_code = 201

        mock_owncloud_put_file = mocker.patch("requests.put")
        mock_owncloud_put_file.return_value.status_code = 201

        from grandma_gcn.database.gw_db import GW_alert as GWDB_alert

        engine, sessionmaker_ = sqlite_engine_and_session
        session = sessionmaker_()
        gw_alert_db = gw_alert_db = GWDB_alert(
            triggerId=S241102_update.event_id,
            thread_ts=None,
            reception_count=1,
            payload_json=S241102_update.gw_dict,
            owncloud_url="https://owncloud.example.com/fake1",
            message_ts="123.456",
            is_process_running=False,
        )
        session.add(gw_alert_db)
        session.commit()
        id_gw_alert_db = gw_alert_db.id_gw
        session.close()

        with patch(
            "grandma_gcn.gcn_stream.gw_alert.Observation_plan_multiple"
        ) as mock_obs_plan:
            mock_obs_plan.return_value = (tiles, MagicMock())

            with patch(
                "grandma_gcn.worker.gwemopt_worker.setup_task_logger"
            ) as mock_logger:
                mock_logger.return_value = (logging.getLogger(), Path("fake_path_log"))

                with patch(
                    "grandma_gcn.worker.celery_app.get_session_local"
                ) as mock_get_session_local:
                    mock_get_session_local.return_value = sessionmaker_
                    with patch(
                        "grandma_gcn.worker.gwemopt_worker.new_alert_on_slack"
                    ) as mock_new_alert:
                        with patch(
                            "grandma_gcn.worker.gwemopt_worker.post_image_on_slack"
                        ) as mock_post_image:
                            mock_post_image.return_value = {
                                "ok": True,
                                "file": {"permalink_public": "https://fake_url"},
                            }
                            mock_new_alert.return_value = {"ts": "dummy_ts"}

                            from sqlalchemy import inspect

                            print("\n\n\n#########################")
                            print("DB URL in test:", engine.url)
                            print(inspect(engine).get_table_names())
                            print("##################\n\n")

                            res_gwemopt = gwemopt_task.apply(
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
                                    id_gw_alert_db,
                                    str(path_output),
                                    str(tmp_path),
                                    {
                                        "BBH_proba": BBH_threshold,
                                        "Distance_cut": Distance_threshold,
                                        "BNS_NSBH_size_cut": ErrorRegion_threshold,
                                        "BBH_size_cut": ErrorRegion_threshold,
                                    },
                                    GW_alert.ObservationStrategy.TILING.value,
                                    "thread_ts",
                                ]
                            )

                        assert mock_obs_plan.called
                        result = res_gwemopt.result
                        assert isinstance(result, tuple)
                        assert "output" in result[0]
                        assert result[1][1].endswith("TILING_TCH_TRE")
                        assert res_gwemopt.traceback is None


def test_process_alert_calls(
    mocker, tiles: dict[str, Table], sqlite_engine_and_session
):
    from grandma_gcn.gcn_stream.consumer import Consumer

    _, sessionmaker_ = sqlite_engine_and_session
    mock_gcn_stream = MagicMock()
    mock_gcn_stream.gcn_config = load_gcn_config(
        Path("tests", "gcn_stream_test.toml"), logger=logging.getLogger()
    )
    mock_gcn_stream.session_local = sessionmaker_()

    notice = open_notice_file(Path("tests"), "S241102br-update.json")

    mock_post_msg_on_slack = mocker.patch(
        "grandma_gcn.slackbot.gw_message.post_msg_on_slack"
    )
    mock_post_msg_on_slack.return_value = {"ts": "dummy_ts"}

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
                    # Patch open for ascii_tiles_path write
                    with patch(
                        "grandma_gcn.worker.gwemopt_worker.open", create=True
                    ) as mock_ascii_open:
                        with patch(
                            "grandma_gcn.worker.celery_app.get_session_local"
                        ) as mock_get_session_local:
                            mock_get_session_local.return_value = sessionmaker_

                            # We mock only the "w" mode for ascii_open
                            # to simulate writing the ascii tiles file.
                            # For other modes, we use the real open function.
                            def open_side_effect(file, mode="r", *args, **kwargs):
                                if mode == "w":
                                    mock_file = MagicMock()
                                    mock_file.__enter__.return_value = MagicMock()
                                    return mock_file
                                else:
                                    # For other modes, use the real open
                                    from builtins import open as real_open

                                    return real_open(file, mode, *args, **kwargs)

                            mock_ascii_open.side_effect = open_side_effect

                            mock_upload.return_value = {
                                "file": {"permalink_public": "https://fake_url"}
                            }

                            mock_open.return_value.__enter__.return_value = MagicMock()
                            mock_obs_plan.return_value = (tiles, MagicMock())

                            # Patch OwncloudClient.mkdir to track calls
                            with patch.object(
                                OwncloudClient,
                                "mkdir",
                                autospec=True,
                                wraps=OwncloudClient.mkdir,
                            ) as spy_mkdir:
                                consumer = Consumer(
                                    gcn_stream=mock_gcn_stream,
                                    logger=logging.getLogger(),
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
    assert mock_post_msg_on_slack.call_count == 10
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
