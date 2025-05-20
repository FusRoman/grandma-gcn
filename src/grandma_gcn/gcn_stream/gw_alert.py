from base64 import b64decode
from enum import Enum
import io
import json
from typing import Any, Self

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
    def __init__(
        self,
        notice: bytes,
        BBH_threshold: float,
        Distance_threshold: float,
        ErrorRegion_threshold: float,
    ) -> None:
        self.gw_dict = bytes_to_dict(notice)

        self.BBH_threshold = BBH_threshold
        self.Distance_threshold = Distance_threshold
        self.ErrorRegion_threshold = ErrorRegion_threshold

    @property
    def event(self) -> dict[str, Any]:
        event = self.gw_dict.get("event", None)
        if event is None:
            return {}
        else:
            return event

    @property
    def event_id(self) -> str:
        """
        Get the identifier of the gw alert

        Returns
        -------
        str
            the gw identifier
        """
        return self.gw_dict["superevent_id"]

    class EventType(Enum):
        RETRACTION = "RETRACTION"
        PRELIMINARY = "PRELIMINARY"
        INITIAL = "INITIAL"
        UPDATE = "UPDATE"

        def to_emoji(self) -> str:
            """
            Convert the event type to an emoji

            Returns
            -------
            str
                the emoji corresponding to the event type
            """
            match self:
                case self.RETRACTION:
                    return "❌"
                case self.PRELIMINARY:
                    return "🟡"
                case self.INITIAL:
                    return "🟢"
                case self.UPDATE:
                    return "🔄"
                case _:
                    return "❓"

    @property
    def event_type(self) -> EventType | None:
        """
        Get the event type of the gw alert

        Returns
        -------
        str
            the event type
        """
        match self.gw_dict["alert_type"]:
            case "RETRACTATION":
                return self.EventType.RETRACTION
            case "PRELIMINARY":
                return self.EventType.PRELIMINARY
            case "INITIAL":
                return self.EventType.INITIAL
            case "UPDATE":
                return self.EventType.UPDATE
            case _:
                return None

    @property
    def event_time(self) -> Time | None:
        event_time = self.event.get("time", None)
        if event_time is None:
            return None
        else:
            return Time(event_time, format="isot")

    @property
    def far(self) -> float | None:
        return self.event.get("far", None)

    @property
    def has_NS(self) -> float | None:
        event_prop: dict[str, float] | None = self.event.get("properties", None)
        if event_prop is None:
            return None
        else:
            return event_prop.get("HasNS", None)

    @property
    def has_remnant(self) -> float | None:
        event_prop: dict[str, float] | None = self.event.get("properties", None)
        if event_prop is None:
            return None
        else:
            return event_prop.get("HasRemnant", None)

    @property
    def is_significant(self) -> bool:
        return self.event.get("significant", False)

    class CBC_proba(Enum):
        BBH = "BBH"
        NSBH = "NSBH"
        BNS = "BNS"
        Terrestrial = "Terrestrial"

        def to_emoji(self) -> str:
            """
            Convert the CBC class to an emoji

            Returns
            -------
            str
                the emoji corresponding to the CBC class
            """
            match self:
                case self.BBH:
                    return "⚫⚫"
                case self.NSBH:
                    return "🌟⚫"
                case self.BNS:
                    return "🌟🌟"
                case self.Terrestrial:
                    return "🌍"
                case _:
                    return "❓"

    def class_proba(self, cbc_class: CBC_proba) -> float | None:
        event_prop: dict[str, float] | None = self.event.get("classification", None)
        if event_prop is None:
            return None
        else:
            return event_prop.get(cbc_class.value, None)

    @property
    def event_class(self) -> CBC_proba | None:
        event_prop: dict[str, float] | None = self.event.get("classification", None)
        if event_prop is None:
            return None
        else:
            match max(event_prop, key=event_prop.get):
                case "Terrestrial":
                    return self.CBC_proba.Terrestrial
                case "BBH":
                    return self.CBC_proba.BBH
                case "NSBH":
                    return self.CBC_proba.NSBH
                case "BNS":
                    return self.CBC_proba.BNS
                case _:
                    return None

    @property
    def group(self) -> str | None:
        return self.event.get("group", None)

    class Instrument(Enum):
        H1 = "H1 (HANFORD)"
        L1 = "L1 (LIVINGSTON)"
        V1 = "V1 (VIRGO)"
        KAGRA = "K1 (KAGRA)"

        @classmethod
        def from_string(cls, instrument: str) -> Self:
            """
            Convert a string to an Instrument enum value

            Parameters
            ----------
            instrument : str
                the instrument string

            Returns
            -------
            Instrument
                the corresponding Instrument enum value
            """
            return cls[instrument] if instrument in cls.__members__ else None

    @property
    def instruments(self) -> Instrument | None:
        """
        Get the instrument used to detect the event

        Returns
        -------
        Instrument
            the instrument used to detect the event
        """
        instrument = self.event.get("instruments", None)
        if instrument is None:
            return None
        else:
            return [self.Instrument.from_string(i) for i in instrument]

    @property
    def gracedb_url(self) -> str | None:
        """
        Get the GraceDB url of the event

        Returns
        -------
        str
            the GraceDB url of the event
        """
        return self.gw_dict["urls"]["gracedb"]

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
        return self.event_id[0] == "S" and self.is_significant

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
    
    class GRANDMA_Action(Enum):
        GO_GRANDMA = "🚀 *GO GRANDMA*"
        NO_GRANDMA = "❌ *NO GRANDMA*"

    def gw_score(self) -> tuple[int, str, GRANDMA_Action]:
        """
        Compute the score of the event based on the event type, class and distance.
        The score is defined as follows:
        - 0: not an astrophysical event
        - 1: terrestrial event
        - 2: interesting event
        - 3: very interesting event

        Parameters
        ----------
        BBH_threshold : float
            the threshold for BBH event (between 0 and 1)
        Distance_threshold : float
            the threshold for distance (in Mpc)
        ErrorRegion_threshold : float
            the threshold for error region (in square degree)

        Returns
        -------
        tuple[int, str, GRANDMA_Action]
            - score: the score of the event
            - msg: a message describing the event
            - conclusion: the action to take based on the score
        """
        # Initialize score to the lowest value
        score = 0
        msg = ""
        conclusion = self.GRANDMA_Action.NO_GRANDMA

        _, size_region, mean_dist, _ = self.get_error_region(0.9)

        match self.event_type:
            case self.EventType.RETRACTION:
                msg = "RETRACTION, it is not an Astrophysical event, \n"
            case (
                self.EventType.PRELIMINARY
                | self.EventType.INITIAL
                | self.EventType.UPDATE
            ):
                match self.event_class:
                    case self.CBC_proba.Terrestrial:
                        msg = (
                            "FA, it might be not an Astrophysical event, \n"
                            "please wait for any retractation message in the next 30 min"
                        )
                    case self.CBC_proba.BBH:
                        if self.class_proba(self.CBC_proba.BBH) > self.BBH_threshold:
                            if (
                                mean_dist < self.Distance_threshold
                                and size_region < self.ErrorRegion_threshold
                            ):
                                msg = "FA, it is a very interesting event, well localized but maybe no counterpart"
                                score = 2
                                conclusion = self.GRANDMA_Action.GO_GRANDMA
                            else:
                                msg = "FA, far and badly localized BBH event"
                                score = 1
                                conclusion = self.GRANDMA_Action.NO_GRANDMA
                    case self.CBC_proba.NSBH | self.CBC_proba.BNS:
                        if (
                            mean_dist < self.Distance_threshold
                            and size_region < self.ErrorRegion_threshold
                        ):
                            msg = "FA, it is a very EXTREMELY interesting event, well localized"
                            score = 3
                            conclusion = self.GRANDMA_Action.GO_GRANDMA
                        else:
                            msg = (
                                "FA, it is a very interesting event, but however well localized and far, "
                                "let's see if we can reach the 50% cred. region."
                            )
                            score = 2
                            conclusion = self.GRANDMA_Action.GO_GRANDMA
                    case _:
                        msg = (
                            "FA, it might be not an Astrophysical event, \n"
                            "please wait for any retractation message in the next 30 min"
                        )
                        score = 0
                        conclusion = self.GRANDMA_Action.NO_GRANDMA

        return score, msg, conclusion
