from pathlib import Path
import pytest

from grandma_gcn.gcn_stream.gw_alert import GW_alert

from astropy.time import Time
from numpy import inf, logical_not, isinf, mean


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


def test_gw_alert_unsignificant(gw_alert_unsignificant: GW_alert):
    assert gw_alert_unsignificant.event_id == "S241004ap"
    assert gw_alert_unsignificant.event_type == GW_alert.EventType.PRELIMINARY
    assert gw_alert_unsignificant.event_time == Time(
        "2024-10-04T06:09:17.813Z", format="isot"
    )
    assert gw_alert_unsignificant.far == 1.4653e-05
    assert gw_alert_unsignificant.has_NS == 0.0
    assert not gw_alert_unsignificant.is_significant

    assert gw_alert_unsignificant.event_class == GW_alert.CBC_proba.Terrestrial
    assert not gw_alert_unsignificant.is_real_observation()
    assert list(gw_alert_unsignificant.get_skymap().columns) == ["UNIQ", "PROBDENSITY"]

    _, size, mean_dist, mean_sigma = gw_alert_unsignificant.get_error_region(0.9)
    assert size == pytest.approx(3613.1591426340738)
    assert mean_dist == inf
    assert mean_sigma == pytest.approx(1.0)

    assert (
        gw_alert_unsignificant.gracedb_url
        == "https://gracedb.ligo.org/superevents/S241004ap/view/"
    )


def test_gw_alert_significant(gw_alert_significant: GW_alert):
    assert gw_alert_significant.event_id == "S241004ap"
    assert gw_alert_significant.event_type == GW_alert.EventType.PRELIMINARY
    assert gw_alert_significant.event_time == Time(
        "2024-10-04T06:09:17.813Z", format="isot"
    )
    assert gw_alert_significant.far == 1.4653e-05
    assert gw_alert_significant.has_NS == 0.0
    assert gw_alert_significant.is_significant

    assert gw_alert_significant.event_class == GW_alert.CBC_proba.Terrestrial
    assert gw_alert_significant.is_real_observation()

    _, size, mean_dist, mean_sigma = gw_alert_significant.get_error_region(0.9)
    assert size == pytest.approx(3613.1591426340738)
    assert mean_dist == inf
    assert mean_sigma == pytest.approx(1.0)

    assert gw_alert_significant.instruments == [
        GW_alert.Instrument.H1,
        GW_alert.Instrument.L1,
    ]


def test_S241102_initial(S241102_initial: GW_alert):
    assert S241102_initial.event_id == "S241102br"
    assert S241102_initial.event_type == GW_alert.EventType.INITIAL
    assert S241102_initial.event_time == Time("2024-11-02T12:40:58.788Z", format="isot")
    assert S241102_initial.far == 1.14177774199959e-41
    assert S241102_initial.has_NS == 0.00013001687588556378
    assert S241102_initial.is_significant

    assert S241102_initial.event_class == GW_alert.CBC_proba.BBH
    assert S241102_initial.is_real_observation()

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

    score, msg, action = S241102_initial.gw_score()
    assert score == 2
    assert (
        msg
        == "FA, it is a very interesting event, well localized but maybe no counterpart"
    )
    assert action == GW_alert.GRANDMA_Action.GO_GRANDMA


def test_S241102_preliminary(S241102_preliminary: GW_alert):
    assert S241102_preliminary.event_id == "S241102br"
    assert S241102_preliminary.event_type == GW_alert.EventType.PRELIMINARY
    assert S241102_preliminary.event_time == Time(
        "2024-11-02T12:40:58.799Z", format="isot"
    )
    assert S241102_preliminary.far == 1.79286773809082e-11
    assert S241102_preliminary.has_NS == 0.0877092915626526
    assert S241102_preliminary.is_significant

    assert S241102_preliminary.event_class == GW_alert.CBC_proba.BBH
    assert S241102_preliminary.is_real_observation()


def test_S241102_update(S241102_update: GW_alert):
    assert S241102_update.event_id == "S241102br"
    assert S241102_update.event_type == GW_alert.EventType.UPDATE
    assert S241102_update.event_time == Time("2024-11-02T12:40:58.788Z", format="isot")
    assert S241102_update.far == 1.14177774199959e-41
    assert S241102_update.has_NS == 0.0
    assert S241102_update.has_remnant == 0.0
    assert S241102_update.is_significant

    assert S241102_update.event_class == GW_alert.CBC_proba.BBH
    assert S241102_update.is_real_observation()
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

    score, msg, action = S241102_update.gw_score()
    assert score == 1
    assert msg == "FA, far and badly localized BBH event"
    assert action == GW_alert.GRANDMA_Action.NO_GRANDMA

    assert S241102_update.instruments == [
        GW_alert.Instrument.H1,
        GW_alert.Instrument.L1,
        GW_alert.Instrument.V1,
    ]


def test_flatten(S241102_update: GW_alert):

    flat_map = S241102_update.flatten_skymap(64)

    not_inf_dist = logical_not(isinf(flat_map["DISTMU"]))

    assert flat_map["PROBDENSITY"].shape == (49152,)
    assert flat_map["PROBDENSITY"].sum() == pytest.approx(0.9999999999999999, rel=1e-2)

    assert flat_map["DISTMU"].shape == (49152,)
    assert mean(flat_map["DISTMU"], where=not_inf_dist) == pytest.approx(
        117.067497400103, rel=1e-2
    )
    assert flat_map["DISTSIGMA"].shape == (49152,)
    assert flat_map["DISTSIGMA"].sum() == pytest.approx(75590.06787484365, rel=1e-2)
    assert flat_map["DISTNORM"].shape == (49152,)
    assert flat_map["DISTNORM"].sum() == pytest.approx(2453462276.0800576, rel=1e-2)
