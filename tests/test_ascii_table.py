import pytest
from astropy.table import Table
from astropy.time import Time
from grandma_gcn.worker.gwemopt_worker import table_to_custom_ascii
import math


def make_table(rows):
    return Table(
        rows=rows,
        names=["rank_id", "tile_id", "RA", "DEC", "Prob", "Timeobs"],
        dtype=[int, int, float, float, float, object],  # object pour Time
    )


def test_table_to_custom_ascii_basic():
    t = make_table(
        [
            (1, 101, 1.0, 0.5, 0.1234, Time("2025-05-27T08:49:22.577")),
            (2, 102, 2.0, 1.0, 0.5678, Time("2025-05-27T09:00:00.123")),
        ]
    )
    result = table_to_custom_ascii("TelescopeA", t)
    lines = result.splitlines()
    assert lines[0] == "# TelescopeA"
    assert "rank_id" in lines[1]
    assert "tile_id" in lines[1]
    assert "RA" in lines[1]
    assert "DEC" in lines[1]
    assert "Prob" in lines[1]
    assert "Timeobs" in lines[1]
    # Check values and formatting
    assert "1" in lines[2]
    assert "101" in lines[2]
    assert "57.2958"[:6] in lines[2]  # RA in deg
    assert "28.6479"[:6] in lines[2]  # DEC in deg
    assert "0.1234" in lines[2]
    assert "2025-05-27 08:49:22.577" in lines[2]
    assert "2" in lines[3]
    assert "102" in lines[3]
    assert "114.5916"[:8] in lines[3]
    assert "57.2958"[:6] in lines[3]
    assert "0.5678" in lines[3]
    assert "2025-05-27 09:00:00.123" in lines[3]


def test_table_to_custom_ascii_empty():
    t = Table(names=["rank_id", "tile_id", "RA", "DEC", "Prob", "Timeobs"])
    result = table_to_custom_ascii("TelescopeB", t)
    assert "# TelescopeB" in result
    assert "# No tiles to observe" in result


def test_table_to_custom_ascii_single_row():
    t = make_table(
        [
            (5, 999, 0.1, -0.1, 0.9999, Time("2023-01-01T00:00:00.999")),
        ]
    )
    result = table_to_custom_ascii("TestScope", t)
    assert "# TestScope" in result
    assert "5" in result
    assert "999" in result
    assert "5.7296" in result  # 0.1 rad in deg
    assert "-5.7296" in result
    assert "0.9999" in result
    assert "2023-01-01 00:00:00.999" in result


def test_table_to_custom_ascii_missing_column():
    t = Table(
        rows=[(1, 101, 1.0, 0.5, 0.1234)],
        names=["rank_id", "tile_id", "RA", "DEC", "Prob"],
    )
    with pytest.raises(KeyError):
        table_to_custom_ascii("TelescopeC", t)


def test_table_to_custom_ascii_time_truncation():
    t = make_table(
        [
            (1, 1, 0.0, 0.0, 1.0, Time("2022-12-31T23:59:59.123456")),
        ]
    )
    result = table_to_custom_ascii("Scope", t)
    # Should truncate to 3 ms digits
    assert "2022-12-31 23:59:59.123" in result
    # Should not contain more than 3 ms digits
    assert "2022-12-31 23:59:59.1234" not in result


def test_table_to_custom_ascii_ra_dec_conversion():
    t = make_table(
        [
            (1, 1, math.pi, -math.pi / 2, 0.5, Time("2022-01-01T12:00:00.000")),
        ]
    )
    result = table_to_custom_ascii("Scope", t)
    # pi rad = 180 deg, -pi/2 = -90 deg
    assert "180.0000" in result
    assert "-90.0000" in result
