import pytest
from astropy.table import Table
from astropy.time import Time
from numpy import inf, isinf, logical_not, mean

from grandma_gcn.gcn_stream.gw_alert import GW_alert


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
    assert not gw_alert_unsignificant.is_real_observation
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
    assert gw_alert_significant.is_real_observation

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
    assert S241102_initial.is_real_observation

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
    assert S241102_preliminary.is_real_observation


def test_S241102_update(S241102_update: GW_alert):
    assert S241102_update.event_id == "S241102br"
    assert S241102_update.event_type == GW_alert.EventType.UPDATE
    assert S241102_update.event_time == Time("2024-11-02T12:40:58.788Z", format="isot")
    assert S241102_update.far == 1.14177774199959e-41
    assert S241102_update.has_NS == 0.0
    assert S241102_update.has_remnant == 0.0
    assert S241102_update.is_significant

    assert S241102_update.event_class == GW_alert.CBC_proba.BBH
    assert S241102_update.is_real_observation
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


def test_gw_score_terrestrial(gw_alert_significant: GW_alert):
    # For a terrestrial event, score should be 0, NO_GRANDMA
    gw_alert_significant.gw_dict["event"]["classification"] = {"Terrestrial": 0.99}
    score, msg, action = gw_alert_significant.gw_score()
    assert score == 0
    assert "not an Astrophysical event" in msg or "please wait" in msg
    assert action == GW_alert.GRANDMA_Action.NO_GRANDMA


def test_gw_score_bbh_far_badly_localized(S241102_update: GW_alert):
    # BBH, far and badly localized, should be score 1, NO_GRANDMA

    S241102_update.thresholds = {
        "BBH_proba": 0.0,  # force threshold to always pass
        "Distance_cut": 1,  # force to fail distance
        "BNS_NSBH_size_cut": 1,  # force to fail region
        "BBH_size_cut": 1,  # force to fail region
    }

    score, msg, action = S241102_update.gw_score()
    assert score == 1
    assert "far and badly localized BBH event" in msg
    assert action == GW_alert.GRANDMA_Action.NO_GRANDMA


def test_gw_score_bbh_interesting(S241102_initial: GW_alert):
    # BBH, well localized and close, should be score 2, GO_GRANDMA

    S241102_initial.thresholds = {
        "BBH_proba": 0.0,  # force threshold to always pass
        "Distance_cut": 1000,  # large enough
        "BNS_NSBH_size_cut": 1000,  # large enough
        "BBH_size_cut": 1000,  # large enough
    }

    score, msg, action = S241102_initial.gw_score()
    assert score == 2
    assert "very interesting event" in msg
    assert action == GW_alert.GRANDMA_Action.GO_GRANDMA


def test_gw_score_bns_extremely_interesting(S241102_initial: GW_alert):
    # Simulate a BNS, well localized and close, should be score 3, GO_GRANDMA
    S241102_initial.gw_dict["event"]["classification"] = {"BNS": 0.99}

    S241102_initial.thresholds = {
        "BBH_proba": 0.0,  # force threshold to always pass
        "Distance_cut": 1000,  # large enough
        "BNS_NSBH_size_cut": 1000,  # large enough
        "BBH_size_cut": 1000,  # large enough
    }

    score, msg, action = S241102_initial.gw_score()
    assert score == 3
    assert "EXTREMELY interesting event" in msg
    assert action == GW_alert.GRANDMA_Action.GO_GRANDMA


def test_gw_score_bns_interesting_far(S241102_initial: GW_alert):
    # Simulate a BNS, far or badly localized, should be score 2, GO_GRANDMA
    S241102_initial.gw_dict["event"]["classification"] = {"BNS": 0.99}

    S241102_initial.thresholds = {
        "BBH_proba": 0.0,  # force threshold to always pass
        "Distance_cut": 1,  # force to fail distance
        "BNS_NSBH_size_cut": 1,  # force to fail region
        "BBH_size_cut": 1,  # force to fail region
    }

    score, msg, action = S241102_initial.gw_score()
    assert score == 2
    assert "very interesting event" in msg
    assert action == GW_alert.GRANDMA_Action.GO_GRANDMA


def test_gw_score_retraction(S241102_initial: GW_alert):
    # Simulate a retraction event
    S241102_initial.gw_dict["alert_type"] = "RETRACTATION"
    score, msg, action = S241102_initial.gw_score()
    assert score == 0
    assert "RETRACTION" in msg
    assert action == GW_alert.GRANDMA_Action.NO_GRANDMA


def test_integrated_proba_percentage_none(S241102_update: GW_alert):
    # Should return 0.0 and log a warning if tiles_table is None
    result = S241102_update.integrated_proba_percentage(None)
    assert result == 0.0


def test_integrated_surface_percentage_none(S241102_update: GW_alert):
    # Should return 0.0 and log a warning if tiles_table is None
    result = S241102_update.integrated_surface_percentage(None)
    assert result == 0.0


def test_integrated_proba_percentage(
    gw_alert_significant: GW_alert, S241102_update: GW_alert, tiles: dict[str, Table]
):
    # Should return the integrated probability percentage for the given tiles
    result = S241102_update.integrated_proba_percentage(tiles["TCH"])
    assert result == pytest.approx(37.19958767563451, rel=1e-4)

    result = gw_alert_significant.integrated_proba_percentage(tiles["TCH"])
    assert result == pytest.approx(37.19825472541179, rel=1e-4)


def test_integrated_surface_percentage(
    gw_alert_significant: GW_alert, S241102_update: GW_alert, tiles: dict[str, Table]
):
    # Should return the integrated surface percentage for the given tiles
    result = S241102_update.integrated_surface_percentage(tiles["TCH"])
    assert result == pytest.approx(25.457746139820987, rel=1e-4)

    result = gw_alert_significant.integrated_surface_percentage(tiles["TCH"])
    assert result == pytest.approx(0.19985883021353368, rel=1e-4)


def test_no_classification(S250720j_update: GW_alert):
    event_class = S250720j_update.event_class
    assert (
        event_class is None
    ), "Event class should be None when no classification is present"
