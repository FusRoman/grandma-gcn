import ast
import io
import json
import logging
import uuid
from base64 import b64decode
from enum import Enum
from pathlib import Path
from typing import Any, Self

import astropy.units as astro_units
import healpy as hp
from astropy.coordinates import SkyCoord
from astropy.table import QTable, Table, unique
from astropy.time import Time
from astropy.units import deg as degree
from astropy_healpix import (
    level_to_nside,
    nside_to_level,
    nside_to_pixel_area,
    uniq_to_level_ipix,
)
from gwemopt.ToO_manager import Observation_plan_multiple
from ligo.skymap.bayestar import rasterize
from numpy import array, cumsum, float64, inf, isinf, logical_not, mean, ndarray, pi
from spherical_geometry.polygon import SphericalPolygon


def bytes_to_dict(notice: bytes) -> dict:
    """
    Convert a bytes notice representing a dict into a python dictionary
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


def save_as_json(dict_notice: dict, save_path: Path) -> None:
    """
    Save a notice as a json file.
    The notice have to be a python dictionary, json compatible.

    Parameters
    ----------
    dict_notice : dict
        The gcn notice
    save_path : Path
        The path where to save the dictionary
    """
    with open(save_path, "w") as fp:
        json.dump(dict_notice, fp)


class GW_alert:
    def __init__(self, notice: bytes, thresholds: dict[str, float | int]) -> None:
        self.gw_dict = bytes_to_dict(notice)
        self.thresholds = thresholds

        self.logger = logging.getLogger(f"gcn_stream.gw_alert_{self.event_id}")

    @property
    def BBH_proba(self) -> float | None:
        """
        Get the terrestrial threshold for the event

        Returns
        -------
        float
            the terrestrial threshold
        """
        return self.thresholds.get("BBH_proba")

    @property
    def BBH_size_cut(self) -> float | None:
        """
        Get the BBH size cut for the event

        Returns
        -------
        float
            the BBH size cut
        """
        return self.thresholds.get("BBH_size_cut")

    @property
    def BNSBH_size_cut(self) -> float | None:
        """
        Get the BNSBH size cut for the event

        Returns
        -------
        float
            the BNSBH size cut
        """
        return self.thresholds.get("BNS_NSBH_size_cut")

    @property
    def Distance_threshold(self) -> float | None:
        """
        Get the distance threshold for the event

        Returns
        -------
        float
            the distance threshold
        """
        return self.thresholds.get("Distance_cut")

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

    @property
    def is_real_observation(self) -> bool:
        """
        Test if the notice is a real observation, meaning that the id start with a S (test notice start with a M
        and are not real gw detection) and is significant.

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
                correspond to the credible level
            - size_region: the size of the region, in square degree
            - mean_distance: the mean of the luminosity distance distribution within the sub region
            - mean_sigma_dist: the mean of the luminosity distance sigma within the sub region
        """
        assert 0 < credible_level <= 1, "credible region must be within 0 and 1"
        skymap = self.get_skymap()
        skymap.sort("PROBDENSITY", reverse=True)
        level, _ = uniq_to_level_ipix(skymap["UNIQ"])
        pixel_area: astro_units.quantity.Quantity = nside_to_pixel_area(
            level_to_nside(level)
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
        GO_GRANDMA = "🚀 *Should we GO GRANDMA ?*"
        NO_GRANDMA = "❌ *PROBABLY NO GRANDMA ?*"

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

        if not self.is_real_observation:
            return score, msg, conclusion

        match self.event_type:
            case self.EventType.RETRACTION:
                msg = "RETRACTION, it is not an Astrophysical event, \n"
            case (
                self.EventType.PRELIMINARY
                | self.EventType.INITIAL
                | self.EventType.UPDATE
            ):
                _, size_region, mean_dist, _ = self.get_error_region(0.9)
                match self.event_class:
                    case self.CBC_proba.Terrestrial:
                        msg = (
                            "FA, it might be not an Astrophysical event, \n"
                            "please wait for any retractation message in the next 30 min"
                        )
                    case self.CBC_proba.BBH:
                        if self.class_proba(self.CBC_proba.BBH) > self.BBH_proba:
                            if (
                                mean_dist < self.Distance_threshold
                                and size_region < self.BBH_size_cut
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
                            and size_region < self.BNSBH_size_cut
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

    def save_notice(self, start_path: Path) -> Path:
        """
        Save a notice as a json file.The filename will be an hexadecimal random value.

        Parameters
        ----------
        start_path : Path
            path where the notice will be saved
        logger : LoggerNewLine, optional
            the logger object, by default None

        Returns
        -------
        str
            the path where the notice has been saved
        """
        notice_id = uuid.uuid4().hex
        path_to_save = Path(start_path, f"{notice_id}.json")
        save_as_json(self.gw_dict, path_to_save)

        self.logger.info(f"New GW notice saved with id={notice_id}")
        return path_to_save

    def flatten_skymap(self, nside_target: int) -> dict:
        """
        Convert a multi-resolution skymap to a flat skymap with a given nside.
        Use the `rasterize` function from `ligo.skymap.bayestar` to flatten the skymap.
        The output skymap is in ring ordering.

        Parameters
        ----------
        nside_target : int
            The target nside for the flat skymap.
        Returns
        -------
        dict
            A dictionary containing the flattened skymap and distance distribution.
            The keys are:
                - "PROBDENSITY": The flattened probability density map.
                - "DISTMU": The flattened distance mean map (if available).
                - "DISTSIGMA": The flattened distance sigma map (if available).
                - "DISTNORM": The flattened distance normalization map (if available).
        """
        skymap = self.get_skymap()
        order = nside_to_level(nside_target)
        flat_map = rasterize(skymap, order)
        flat_map.rename_column("PROB", "PROBDENSITY")
        for cols in flat_map.colnames:
            flat_map[cols] = hp.reorder(flat_map[cols], n2r=True)
        return flat_map

    class ObservationStrategy(Enum):
        TILING = "Tiling"
        GALAXYTARGETING = "Galaxy targeting"

        @classmethod
        def from_string(cls, strategy: str) -> Self:
            """
            Convert a string to an ObservationStrategy enum value

            Parameters
            ----------
            strategy : str
                the observation strategy string

            Returns
            -------
            ObservationStrategy
                the corresponding ObservationStrategy enum value
            """
            match strategy:
                case "Tiling":
                    return cls.TILING
                case "Galaxy targeting":
                    return cls.GALAXYTARGETING
                case _:
                    raise ValueError(
                        f"Unknown observation strategy: {strategy}. "
                        "Expected 'Tiling' or 'Galaxy targeting'."
                    )

        def to_emoji(self) -> str:
            """
            Convert the observation strategy to an emoji

            Returns
            -------
            str
                the emoji corresponding to the observation strategy
            """
            match self:
                case self.TILING:
                    return "🧱"
                case self.GALAXYTARGETING:
                    return "🌌"
                case _:
                    return "❓"

    def run_observation_plan(
        self,
        telescope_list: list[str],
        params: dict[str, Any],
        map_struct: dict[str, Any],
        path_output: str,
        observation_strategy: ObservationStrategy,
    ) -> tuple[Table, Any]:
        """
        Launch the gwemopt process with the given parameters and skymap structure.
        Becareful, the input map ordering have to be in nested order.

        Parameters
        ----------
        telescope_list : list[str]
            The list of telescopes to use for the observation.
        params : dict[str, Any]
            The parameters for the gwemopt process.
        map_struct : dict[str, Any]
            The skymap structure.
        path_output : str
            The path where the output will be saved.
        observation_strategy : ObservationStrategy
            The observation strategy to use (TILING or GALAXYTARGETING).

        Returns
        -------
        tuple[Table, Any]
            - tiles_tables: the table of tiles generated by gwemopt
            - galaxies_table: the table of galaxies generated by gwemopt
        """

        return Observation_plan_multiple(
            telescope_list,
            self.get_event_time(),
            self.event_id,
            params,
            map_struct,
            observation_strategy.value,
            path_output,
        )

    def integrated_proba_percentage(
        self, tiles_table: Table | None
    ) -> tuple[float, float]:
        """
        Compute the percentage of probability density covered by the tiles on the skymap.
        This function computes the percentage of the total probability density of the skymap
        that is covered by the tiles generated by gwemopt. It uses the PROBDENSITY and UNIQ
        columns from the skymap to calculate the total probability density and the area of the tiles.

        Parameters
        ----------
        tiles_table : Table
            The table of tiles generated by gwemopt.

        Returns
        -------
        float
            The percentage of probability density covered by the tiles.
            Is 0.0 if no tiles table is provided.
        """
        if not tiles_table:
            self.logger.warning(
                "No tiles table provided, cannot compute coverage percentage."
            )
            return 0.0

        skymap, _, _, _ = self.get_error_region(0.9)
        skymap.sort("PROBDENSITY", reverse=True)
        level, _ = uniq_to_level_ipix(skymap["UNIQ"])
        pixel_area: astro_units.quantity.Quantity = nside_to_pixel_area(
            level_to_nside(level)
        )

        prob = pixel_area * skymap["PROBDENSITY"]

        unique_tiles = unique(tiles_table, keys="tile_id", keep="first")
        prob_covered = sum(unique_tiles["prob_sum"])

        integrated_proba_percentage = ((prob_covered / sum(prob)) * 100).value

        return integrated_proba_percentage

    def integrated_surface_percentage(self, tiles_table: Table | None) -> float:
        """
        Compute the percentage of surface area covered by the tiles on the skymap.

        This function computes the percentage of the total surface area of the skymap
        that is covered by the tiles generated by gwemopt. It uses the UNIQ column from
        the skymap to calculate the total surface area and the area of the tiles.
        The function returns the percentage of coverage as a float.

        Parameters
        ----------
        tiles_table : Table
            The table of tiles generated by gwemopt.

        Returns
        -------
        float
            The percentage of surface area covered by the tiles.
        """
        if not tiles_table:
            self.logger.warning(
                "No tiles table provided, cannot compute coverage percentage."
            )
            return 0.0

        _, size_skymap, _, _ = self.get_error_region(0.9)

        surfaces_tuiles = []
        unique_tiles = unique(tiles_table, keys="tile_id", keep="first")

        for row in unique_tiles:
            corners = ast.literal_eval(row["Corners"])
            ra = [p[0] for p in corners]
            dec = [p[1] for p in corners]

            coord = SkyCoord(ra=ra * degree, dec=dec * degree, frame="icrs")
            poly = SphericalPolygon.from_radec(coord.ra, coord.dec)
            surfaces_tuiles.append(poly.area() * ((180 / pi) ** 2))

        surface_tuiles_totale = sum(surfaces_tuiles)
        return (surface_tuiles_totale / size_skymap) * 100
