from pathlib import Path
import pickle

import pytest

from grandma_gcn.gcn_stream.gcn_logging import init_logging
from grandma_gcn.gcn_stream.gw_alert import GW_alert
from astropy.table import Table


@pytest.fixture(autouse=True)
def set_fake_slack_token(monkeypatch, request):
    if "e2e" in request.keywords:
        yield
    else:
        monkeypatch.setenv("FINK_SLACK_TOKEN", "fake-token-for-tests")
        yield


@pytest.fixture
def logger():
    """
    Fixture to initialize the logger
    """
    return init_logging()


@pytest.fixture
def gcn_config_path():
    """
    Fixture to provide the path to the GCN configuration file
    """
    return Path("tests/gcn_stream_test.toml")


@pytest.fixture
def path_tests():
    basedir = Path.absolute(Path(__file__).parents[1])
    return Path(basedir, "tests")


def open_notice_file(path_test, name_file):
    path_notice = Path(path_test, "notice_examples", name_file)
    with open(path_notice, "rb") as fp:
        return fp.read()


@pytest.fixture
def threshold_config() -> dict[str, float]:
    """
    Fixture to provide the threshold configuration for GW alerts
    """
    return {
        "BBH_proba": 0.5,  # between 0 and 1
        "Distance_cut": 100,  # in Mpc
        "BNS_NSBH_size_cut": 100,  # in deg²
        "BBH_size_cut": 100,  # in deg²
    }


@pytest.fixture
def gw_alert_unsignificant(path_tests, threshold_config) -> GW_alert:
    bytes_notice = open_notice_file(path_tests, "gw_notice_unsignificant.json")
    return GW_alert(bytes_notice, thresholds=threshold_config)


@pytest.fixture
def gw_alert_significant(path_tests, threshold_config) -> GW_alert:
    bytes_notice = open_notice_file(path_tests, "gw_notice_significant.json")
    return GW_alert(bytes_notice, thresholds=threshold_config)


@pytest.fixture
def S241102_initial(
    path_tests,
) -> GW_alert:
    bytes_notice = open_notice_file(path_tests, "S241102br-initial.json")
    specific_thresholds = {
        "BBH_proba": 0.5,  # between 0 and 1
        "Distance_cut": 500,  # in Mpc
        "BNS_NSBH_size_cut": 100,  # in deg²
        "BBH_size_cut": 100,  # in deg²
    }
    return GW_alert(bytes_notice, thresholds=specific_thresholds)


@pytest.fixture
def S241102_preliminary(path_tests, threshold_config) -> GW_alert:
    bytes_notice = open_notice_file(path_tests, "S241102br-preliminary.json")
    return GW_alert(bytes_notice, thresholds=threshold_config)


@pytest.fixture
def S241102_update(path_tests, threshold_config) -> GW_alert:
    bytes_notice = open_notice_file(path_tests, "S241102br-update.json")
    return GW_alert(bytes_notice, thresholds=threshold_config)


@pytest.fixture
def owncloud_client(gcn_config_path, logger):
    """
    Fixture to create an instance of OwncloudClient
    """
    from grandma_gcn.worker.owncloud_client import OwncloudClient
    from grandma_gcn.gcn_stream.stream import load_gcn_config

    config = load_gcn_config(gcn_config_path, logger=logger)
    return OwncloudClient(config.get("OWNCLOUD"))


@pytest.fixture
def tiles() -> dict[str, Table]:
    return pickle.load(open("tests/data/tiles.pickle", "rb"))
