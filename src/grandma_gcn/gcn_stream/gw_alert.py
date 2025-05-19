from base64 import b64decode
from enum import Enum
import io
import json
from typing import Any

from astropy.time import Time

from astropy.table import QTable
import astropy.units as astro_units
from numpy import array, cumsum, float64, inf, isinf, logical_not, mean, ndarray


def bytes_to_dict(notice: bytes) -> dict:
    """
    Convert a bytes notice representing a dict into a python dictionnary
    Convert also the potential string value into real python literal.

    Parameters
    ----------
    notice : str
        GCN notice represented as a dictionary

    Returns
    -------
    dict
        the notice dictionary
    """
    return json.load(io.BytesIO(notice))


class GW_alert:
    def __init__(self, notice: bytes) -> None:
        self.gw_dict = bytes_to_dict(notice)

    @property
    def event(self) -> dict[str, Any]:
        event = self.gw_dict.get("event", None)
        if event is None:
            return {}
        else:
            return event

    def get_id(self) -> str:
        """
        Get the identifier of the gw alert

        Returns
        -------
        str
            the gw identifier
        """
        return self.gw_dict["superevent_id"]

    @property
    def event_time(self) -> Time | None:
        event_time = self.event.get("time", None)
        if event_time is None:
            return None
        else:
            return Time(event_time, format="isot")

    @property
    def far(self) -> float | None:
        event_far = self.event.get("far", None)
        if event_far is None:
            return None
        else:
            return event_far

    @property
    def has_NS(self) -> float | None:
        event_prop: dict[str, float] | None = self.event.get("properties", None)
        if event_prop is None:
            return None
        else:
            return event_prop.get("HasNS", None)

    @property
    def is_significant(self) -> bool:
        return self.event.get("significant", False)

    class CBC_proba(Enum):
        BBH = "BBH"
        NSBH = "NSBH"
        BNS = "BNS"

    def class_proba(self, cbc_class: CBC_proba) -> float | None:
        event_prop: dict[str, float] | None = self.event.get("classification", None)
        if event_prop is None:
            return None
        else:
            return event_prop.get(cbc_class.value, None)

    @property
    def event_class(self) -> str | None:
        event_prop: dict[str, float] | None = self.event.get("classification", None)
        if event_prop is None:
            return None
        else:
            return max(event_prop, key=event_prop.get)

    def get_event_time(self) -> Time | None:
        """
        Return the event time in UTC.

        Returns
        -------
        Time
            the event time as an astropy time object
        """
        return self.event_time

    def is_real_observation(self) -> bool:
        """
        Test if the notice is a real observation, meaning that the id start with a S, test notice start with a M
        and are not real gw detection.

        Returns
        -------
        bool
            if True, the notice is a real detection.
        """
        return self.get_id()[0] == "S" and self.is_significant

    def get_skymap(self) -> QTable:
        """
        Load and decode the skymap contains within the notice.

        Returns
        -------
        QTable
            the gravitational wave skymap
        """
        skymap_str = self.gw_dict["event"]["skymap"]
        skymap_bytes = b64decode(skymap_str)
        skymap: QTable = QTable.read(io.BytesIO(skymap_bytes))
        return skymap

    def get_error_region(
        self, credible_level: float
    ) -> tuple[QTable, float64, float64, float64]:
        """
        Return the skymap region corresponding to the credible level,
        the size of the region and the mean luminosity distance

        Parameters
        ----------
        credible_level : float
            the credible level used to extract the sub skymap region.

        Returns
        -------
        tuple[QTable, float64, float64, float64]
            - skymap_region: the portion of the skymap where the cumulative probability distribition
                correpond to the credible level
            - size_region: the size of the region, in square degree
            - mean_distance: the mean of the luminosity distance distribution within the sub region
            - mean_sigma_dist: the mean of the luminosity distance sigma within the sub region
        """
        import astropy_healpix as ah

        assert 0 < credible_level <= 1, "credible region must be within 0 and 1"
        skymap = self.get_skymap()
        skymap.sort("PROBDENSITY", reverse=True)
        level, _ = ah.uniq_to_level_ipix(skymap["UNIQ"])
        pixel_area: astro_units.quantity.Quantity = ah.nside_to_pixel_area(
            ah.level_to_nside(level)
        )

        prob = pixel_area * skymap["PROBDENSITY"]
        cumprob: ndarray = cumsum(prob)

        i = cumprob.searchsorted(credible_level)

        skymap_region = skymap[:i]
        size_region = pixel_area[:i].sum()

        if "DISTMU" in skymap_region.colnames:
            distmu = array(skymap_region["DISTMU"])
            distsigma = array(skymap_region["DISTSIGMA"])

            not_inf_dist = logical_not(isinf(distmu))
            not_1_sigma = distsigma != 1.0
            mean_distance = mean(distmu, where=not_inf_dist)
            mean_sigma_dist = mean(distsigma, where=not_1_sigma)
        else:
            mean_distance = inf
            mean_sigma_dist = 1.0

        return (
            skymap_region,
            size_region.to_value(astro_units.degree**2),
            mean_distance,
            mean_sigma_dist,
        )
