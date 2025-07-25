from grandma_gcn.gcn_stream.gw_alert import GW_alert
from grandma_gcn.slackbot.gw_message import build_gwalert_data_msg


def test_build_gwalert_data_msg_branches(
    S250720j_update: GW_alert, S241102_update: GW_alert
):
    path_gw_alert = "S250720j_update"
    nb_alert_received = 1
    msg = build_gwalert_data_msg(S250720j_update, path_gw_alert, nb_alert_received)
    assert msg is not None
    assert hasattr(msg, "blocks")
    blocks = msg.blocks["blocks"]

    header_blocks = [block for block in blocks if block.get("type") == "header"]
    assert any(
        "N°1" in block.get("text", {}).get("text", "") for block in header_blocks
    )

    assert any("GRANDMA Score" in str(block) for block in blocks)
    assert any("Decision time" in str(block) for block in blocks)

    assert any("SkyPortal" in str(block) for block in blocks)
    assert any("GraceDB" in str(block) for block in blocks)
    assert any("OwnCloud" in str(block) for block in blocks)

    assert any("Instruments" in str(block) for block in blocks)
    assert any("No classification available" in str(block) for block in blocks)
    assert not any("Preferred class" in str(block) for block in blocks)
    assert not any("Other classes" in str(block) for block in blocks)

    msg = build_gwalert_data_msg(S241102_update, path_gw_alert, nb_alert_received)
    blocks = msg.blocks["blocks"]
    assert any("Preferred class" in str(block) for block in blocks)
    assert any("Other classes" in str(block) for block in blocks)
    assert not any("No classification available" in str(block) for block in blocks)
