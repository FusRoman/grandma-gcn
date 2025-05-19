from pathlib import Path
import pytest

from grandma_gcn.gcn_stream.gw_alert import GW_alert

from astropy.time import Time


@pytest.fixture
def path_tests():
    basedir = Path.absolute(Path(__file__).parents[1])
    return Path(basedir, "tests")


def open_notice_file(path_test, name_file):
    path_notice = Path(path_test, "notice_examples", name_file)
    print(f"Opening {path_notice}")
    with open(path_notice, "rb") as fp:
        return fp.read()


@pytest.fixture
def gw_alert_unsignificant(
    path_tests,
):
    bytes_notice = open_notice_file(path_tests, "gw_notice_unsignificant.json")
    return GW_alert(bytes_notice)


@pytest.fixture
def gw_alert_significant(
    path_tests,
):
    bytes_notice = open_notice_file(path_tests, "gw_notice_significant.json")
    return GW_alert(
        bytes_notice,
    )


@pytest.fixture
def S241102_initial(
    path_tests,
):
    bytes_notice = open_notice_file(path_tests, "S241102br-initial.json")
    return GW_alert(
        bytes_notice,
    )


@pytest.fixture
def S241102_preliminary(
    path_tests,
):
    bytes_notice = open_notice_file(path_tests, "S241102br-preliminary.json")
    return GW_alert(
        bytes_notice,
    )


@pytest.fixture
def S241102_update(
    path_tests,
):
    bytes_notice = open_notice_file(path_tests, "S241102br-update.json")
    return GW_alert(
        bytes_notice,
    )


def test_gw_alert_unsignificant(gw_alert_unsignificant):
    assert gw_alert_unsignificant.get_id() == "S241004ap"
    assert gw_alert_unsignificant.event_time == Time(
        "2024-10-04T06:09:17.813Z", format="isot"
    )
    assert gw_alert_unsignificant.far == 1.4653e-05
    assert gw_alert_unsignificant.has_NS == 0.0
    assert gw_alert_unsignificant.is_significant == False

    assert gw_alert_unsignificant.event_class == "Terrestrial"
    assert gw_alert_unsignificant.is_real_observation() == False
    assert list(gw_alert_unsignificant.get_skymap().columns) == ["UNIQ", "PROBDENSITY"]


def test_gw_alert_significant(gw_alert_significant):
    assert gw_alert_significant.get_id() == "S241004ap"
    assert gw_alert_significant.event_time == Time(
        "2024-10-04T06:09:17.813Z", format="isot"
    )
    assert gw_alert_significant.far == 1.4653e-05
    assert gw_alert_significant.has_NS == 0.0
    assert gw_alert_significant.is_significant == True

    assert gw_alert_significant.event_class == "Terrestrial"
    assert gw_alert_significant.is_real_observation() == True


def test_S241102_initial(S241102_initial):
    assert S241102_initial.get_id() == "S241102br"
    assert S241102_initial.event_time == Time("2024-11-02T12:40:58.788Z", format="isot")
    assert S241102_initial.far == 1.14177774199959e-41
    assert S241102_initial.has_NS == 0.00013001687588556378
    assert S241102_initial.is_significant == True

    assert S241102_initial.event_class == "BBH"
    assert S241102_initial.is_real_observation() == True

    skymap, size, mean_dist, mean_sigma = S241102_initial.get_error_region(0.9)
    assert list(skymap.columns) == [
        "UNIQ",
        "PROBDENSITY",
        "DISTMU",
        "DISTSIGMA",
        "DISTNORM",
    ]
    assert size == pytest.approx(44.86286812917817)
    assert mean_dist == pytest.approx(330.4256747346908)
    assert mean_sigma == pytest.approx(64.22139243815457)


def test_S241102_preliminary(S241102_preliminary):
    assert S241102_preliminary.get_id() == "S241102br"
    assert S241102_preliminary.event_time == Time(
        "2024-11-02T12:40:58.799Z", format="isot"
    )
    assert S241102_preliminary.far == 1.79286773809082e-11
    assert S241102_preliminary.has_NS == 0.0877092915626526
    assert S241102_preliminary.is_significant == True

    assert S241102_preliminary.event_class == "BBH"
    assert S241102_preliminary.is_real_observation() == True


def test_S241102_update(S241102_update):
    assert S241102_update.get_id() == "S241102br"
    assert S241102_update.event_time == Time("2024-11-02T12:40:58.788Z", format="isot")
    assert S241102_update.far == 1.14177774199959e-41
    assert S241102_update.has_NS == 0.0
    assert S241102_update.is_significant == True

    assert S241102_update.event_class == "BBH"
    assert S241102_update.is_real_observation() == True
    assert list(S241102_update.get_skymap().columns) == [
        "UNIQ",
        "PROBDENSITY",
        "DISTMU",
        "DISTSIGMA",
        "DISTNORM",
    ]

    skymap, size, mean_dist, mean_sigma = S241102_update.get_error_region(0.9)
    assert list(skymap.columns) == [
        "UNIQ",
        "PROBDENSITY",
        "DISTMU",
        "DISTSIGMA",
        "DISTNORM",
    ]
    assert size == pytest.approx(28.36550241549616)
    assert mean_dist == pytest.approx(347.88440663115614)
    assert mean_sigma == pytest.approx(55.28044894083562)
