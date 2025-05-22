from grandma_gcn.gcn_stream.gw_alert import GW_alert
from grandma_gcn.worker.gwemopt_launcher import init_gwemopt


def test_init_gwemopt_basic(gw_alert_unsignificant: GW_alert):
    nside = 16
    flat_map = gw_alert_unsignificant.flatten_skymap(nside)

    params, map_struct = init_gwemopt(
        flat_map,
        exposure_time=100,
        max_nb_tile=10,
        nside=nside,
        do_3d=False,
        do_plot=False,
        do_observability=False,
        do_footprint=False,
        do_movie=False,
        moon_check=False,
        do_reference=True,
    )

    # Vérification des paramètres (inchangé)
    assert isinstance(params, dict)
    assert params["exposuretimes"] == [100, 100, 100, 100]
    assert params["max_nb_tiles"] == [10, 10, 10, 10]
    assert params["nside"] == nside
    assert params["do3D"] is False
    assert params["doPlots"] is False
    assert params["doObservability"] is False
    assert params["doFootprint"] is False
    assert params["doMovie"] is False
    assert params["Moon_check"] is False
    assert params["doReferences"] is True

    # Vérification détaillée de la structure de la carte
    assert isinstance(map_struct, dict)
    # Champs obligatoires
    for key in [
        "prob",
        "ra",
        "dec",
        "cumprob",
        "ipix_keep",
        "nside",
        "npix",
        "pixarea",
        "pixarea_deg2",
    ]:
        assert key in map_struct, f"Clé manquante dans map_struct: {key}"

    # Types et cohérence des shapes
    assert hasattr(map_struct["prob"], "shape")
    assert map_struct["prob"].ndim == 1
    assert map_struct["ra"].shape == map_struct["dec"].shape == map_struct["prob"].shape

    # Validité des valeurs
    assert (map_struct["prob"] >= 0).all()
    assert map_struct["prob"].sum() > 0
    assert map_struct["nside"] == nside
    assert map_struct["npix"] == len(map_struct["prob"])
    assert map_struct["pixarea_deg2"] > 0

    # Vérification des champs optionnels si présents (3D)
    for key in ["distmu", "distsigma", "distnorm"]:
        assert map_struct[key] is None


def test_init_gwemopt_S241102_update(S241102_update: GW_alert):
    nside = 16
    flat_map = S241102_update.flatten_skymap(nside)

    params, map_struct = init_gwemopt(
        flat_map,
        exposure_time=100,
        max_nb_tile=10,
        nside=nside,
        do_3d=False,
        do_plot=False,
        do_observability=False,
        do_footprint=False,
        do_movie=False,
        moon_check=False,
        do_reference=True,
    )

    # Vérification des paramètres
    assert isinstance(params, dict)
    assert params["exposuretimes"] == [100, 100, 100, 100]
    assert params["max_nb_tiles"] == [10, 10, 10, 10]
    assert params["nside"] == nside
    assert params["do3D"] is False
    assert params["doPlots"] is False
    assert params["doObservability"] is False
    assert params["doFootprint"] is False
    assert params["doMovie"] is False
    assert params["Moon_check"] is False
    assert params["doReferences"] is True

    # Vérification détaillée de la structure de la carte
    assert isinstance(map_struct, dict)
    for key in [
        "prob",
        "ra",
        "dec",
        "cumprob",
        "ipix_keep",
        "nside",
        "npix",
        "pixarea",
        "pixarea_deg2",
    ]:
        assert key in map_struct, f"Clé manquante dans map_struct: {key}"

    # Types et cohérence des shapes
    assert hasattr(map_struct["prob"], "shape")
    assert map_struct["prob"].ndim == 1
    assert map_struct["ra"].shape == map_struct["dec"].shape == map_struct["prob"].shape

    # Validité des valeurs
    assert (map_struct["prob"] >= 0).all()
    assert map_struct["prob"].sum() > 0
    assert map_struct["nside"] == nside
    assert map_struct["npix"] == len(map_struct["prob"])
    assert map_struct["pixarea_deg2"] > 0

    # Vérification des champs optionnels si présents (3D)
    for key in ["distmu", "distsigma", "distnorm"]:
        assert map_struct[key].shape == map_struct["prob"].shape
