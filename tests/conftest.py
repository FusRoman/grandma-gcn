from pathlib import Path

import pytest

from grandma_gcn.gcn_stream.gcn_logging import init_logging
from grandma_gcn.gcn_stream.gw_alert import GW_alert


@pytest.fixture(autouse=True)
def set_fake_slack_token(monkeypatch):
    monkeypatch.setenv("FINK_SLACK_TOKEN", "fake-token-for-tests")


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
def gw_alert_unsignificant(
    path_tests,
) -> GW_alert:
    bytes_notice = open_notice_file(path_tests, "gw_notice_unsignificant.json")
    return GW_alert(bytes_notice, 0.5, 100, 100)


@pytest.fixture
def gw_alert_significant(
    path_tests,
) -> GW_alert:
    bytes_notice = open_notice_file(path_tests, "gw_notice_significant.json")
    return GW_alert(bytes_notice, 0.5, 100, 100)


@pytest.fixture
def S241102_initial(
    path_tests,
) -> GW_alert:
    bytes_notice = open_notice_file(path_tests, "S241102br-initial.json")
    return GW_alert(bytes_notice, 0.5, 500, 100)


@pytest.fixture
def S241102_preliminary(
    path_tests,
) -> GW_alert:
    bytes_notice = open_notice_file(path_tests, "S241102br-preliminary.json")
    return GW_alert(bytes_notice, 0.5, 100, 100)


@pytest.fixture
def S241102_update(
    path_tests,
) -> GW_alert:
    bytes_notice = open_notice_file(path_tests, "S241102br-update.json")
    return GW_alert(bytes_notice, 0.5, 100, 100)
