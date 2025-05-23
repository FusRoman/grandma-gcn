from typing import Any

from numpy import ndarray

from gwemopt.utils import read_skymap
from healpy import reorder


def make_params(
    exposure_time: list[int],
    max_nb_tile: list[int],
    nside: int,
    do_3d: bool,
    do_plot: bool,
    do_observability: bool,
    do_footprint: bool,
    do_movie: bool,
    moon_check: bool,
    do_reference: bool,
) -> dict[str, Any]:
    """
    Create the parameters for the gwemopt launcher.
    Parameters
    ----------
    exposure_time : list[int]
        Exposure time in seconds.
    max_nb_tile : list[int]
        Maximum number of tiles.
    nside : int
        Nside parameter for HEALPix.
    do_3d : bool
        Whether to use 3D mode.
    do_plot : bool
        Whether to generate plots.
    do_observability : bool
        Whether to check observability.
    do_footprint : bool
        Whether to generate footprint.
    do_movie : bool
        Whether to create a movie.
    moon_check : bool
        Whether to check for moon interference.
    do_reference : bool
        Whether to use reference images.
    Returns
    -------
    dict[str, Any]
        A dictionary containing the parameters for the gwemopt launcher.
    """
    return {
        "config": {},
        "gpstime": None,
        "galactic_limit": 0.0,
        "confidence_level": 0.9,
        "powerlaw_cl": 0.9,
        "powerlaw_n": 1.0,
        "powerlaw_dist_exp": 1.0,
        "doPlots": do_plot,
        "doMovie": do_movie,
        "doObservability": do_observability,
        "do3D": do_3d,
        "DScale": 1.0,
        "doFootprint": do_footprint,
        "footprint_ra": 30.0,
        "footprint_dec": 60.0,
        "footprint_radius": 10.0,
        "airmass": 2.5,
        "doRASlice": False,
        "doRotate": False,
        "AGN_flag": False,
        "doOrderByObservability": False,
        "doTreasureMap": False,
        "doUpdateScheduler": False,
        "doBlocks": False,
        "doSuperSched": False,
        "doBalanceExposure": False,
        "doMovie_supersched": False,
        "doCommitDatabase": False,
        "doRequestScheduler": False,
        "dateobs": False,
        "doEvent": False,
        "doSkymap": True,
        "doDatabase": False,
        "doReferences": do_reference,
        "doChipGaps": False,
        "doSplit": False,
        "doSchedule": False,
        "doMinimalTiling": True,
        "doIterativeTiling": False,
        "doMaxTiles": True,
        "iterativeOverlap": 0.2,
        "maximumOverlap": 0.2,
        "catalog_n": 1.0,
        "doUseCatalog": False,
        "catalogDir": "/home/roman/Documents/Work/too-mm/configs_gwemopt/catalogs/",
        "tilingDir": "/home/roman/Documents/Work/too-mm/configs_gwemopt/tiling/",
        "configDirectory": "/home/roman/Documents/Work/too-mm/configs_gwemopt/config/",
        "galaxy_catalog": "mangrove",
        "doCatalog": False,
        "galaxy_grade": "Smass",
        "writeCatalog": False,
        "doParallel": False,
        "Ncores": 2,
        "doAlternatingFilters": False,
        "galaxies_FoV_sep": 0.9,
        "doOverlappingScheduling": False,
        "doPerturbativeTiling": False,
        "doSingleExposure": True,
        "filters": ["g"],
        "exposuretimes": exposure_time,
        "mindiff": 1800.0,
        "Moon_check": moon_check,
        "nside": nside,
        "max_nb_tiles": max_nb_tile,
    }


def init_gwemopt(
    flat_skymap: dict[str, ndarray],
    convert_to_nested: bool,
    exposure_time: list[int],
    max_nb_tile: list[int],
    nside: int,
    do_3d: bool,
    do_plot: bool,
    do_observability: bool,
    do_footprint: bool,
    do_movie: bool,
    moon_check: bool,
    do_reference: bool,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """
    Start the gwemopt launcher with the given parameters.

    Parameters
    ----------
    flat_skymap : dict[str, ndarray]
        The flattened skymap data in ring ordering.
    convert_to_nested : bool
        Whether to convert the skymap to nested ordering.
    exposure_time : int
        Exposure time in seconds.
    max_nb_tile : int
        Maximum number of tiles.
    nside : int
        Nside parameter for HEALPix.
    do_3d : bool
        Whether to use 3D mode.
    do_plot : bool
        Whether to generate plots.
    do_observability : bool
        Whether to check observability.
    do_footprint : bool
        Whether to generate footprint.
    do_movie : bool
        Whether to create a movie.
    moon_check : bool
        Whether to check for moon interference.
    do_reference : bool
        Whether to use reference images.

    Returns
    -------
    tuple[dict[str, Any], dict[str, Any]]
        A tuple containing the parameters and the skymap structure.
    """
    params = make_params(
        exposure_time,
        max_nb_tile,
        nside,
        do_3d,
        do_plot,
        do_observability,
        do_footprint,
        do_movie,
        moon_check,
        do_reference,
    )

    if convert_to_nested:
        # Convert the flat skymap to nested ordering
        flat_skymap = {k: reorder(v, n2r=True) for k, v in flat_skymap.items()}

    map_struct = read_skymap(params, is3D=params["do3D"], flat_skymap=flat_skymap)

    return params, map_struct
