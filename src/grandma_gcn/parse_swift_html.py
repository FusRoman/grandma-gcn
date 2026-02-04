"""
Parser for SWIFT BAT GRB HTML result pages.

Extracts key parameters from SWIFT GRB analysis pages:
- T90 duration
- Hardness ratio
- Fluence values
- Peak flux
- Spectral characteristics
"""

import re

import requests
from bs4 import BeautifulSoup
from fink_utils.slack_bot.msg_builder import Message

from grandma_gcn.slackbot.element_extension import BaseSection, MarkdownText


def parse_swift_grb_html(trigger_id: int) -> dict[str, any]:
    """
    Parse SWIFT BAT GRB HTML page to extract key parameters.

    Args:
        trigger_id: SWIFT trigger ID (e.g., 1423875)

    Returns:
        Dictionary containing extracted parameters:
        {
            't90': float or None,  # seconds (15-150 keV)
            't90_error': float or None,  # seconds
            't90_50_300': float or None,  # seconds (BATSE band)
            'hardness_ratio': float or None,  # energy fluence ratio
            'fluence_15_150': float or None,  # erg/cm²
            'fluence_15_150_error': float or None,  # erg/cm²
            'raw_html': str  # first 1000 chars for debugging
        }
    """
    url = (
        f"https://swift.gsfc.nasa.gov/results/BATbursts/{trigger_id}/bascript/top.html"
    )
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    html_content = response.text

    soup = BeautifulSoup(html_content, "html.parser")

    result = {
        "t90": None,
        "t90_error": None,
        "t90_50_300": None,  # T90 in BATSE band (50-300 keV)
        "hardness_ratio": None,
        "fluence_15_150": None,
        "raw_html": html_content[:1000],  # Store first 1000 chars for debugging
    }

    text = soup.get_text()

    # Extract T90 duration (main, 15-150 keV) "T90: X +/- Y"
    t90_match = re.search(r"T90:\s+([0-9.]+)\s+\+/-\s+([0-9.]+)", text)
    if t90_match:
        result["t90"] = float(t90_match.group(1))
        result["t90_error"] = float(t90_match.group(2))

    # Extract T90 in 50-300 keV band (BATSE band)
    t90_batse_match = re.search(
        r"T90\s+in\s+the\s+50-300\s+keV\s+band:\s+([0-9.]+)\s+sec", text
    )
    if t90_batse_match:
        result["t90_50_300"] = float(t90_batse_match.group(1))

    # Extract Hardness Ratio (energy fluence ratio) = X.XXXX
    hr_match = re.search(
        r"[Hh]ardness\s+ratio\s*\(?energy fluence ratio\)?\s*[=:]\s*([0-9.]+)", text
    )
    if hr_match:
        result["hardness_ratio"] = float(hr_match.group(1))

    # Extract Fluence (15-150 keV) from the 1-second peak energy fluence table
    # section "in 1 sec:" followed by "Single BB" -> "Spectral model blackbody"
    fluence_section = re.search(
        r"in\s+1\s+sec:.*?Spectral\s+model\s+blackbody:.*?Energy\s+Fluence\s+90%\s+Error.*?\[keV\].*?\[erg/cm2\].*?\[erg/cm2\].*?15-\s*150\s+([0-9.]+e[+-]?[0-9]+)",
        text,
        re.DOTALL | re.IGNORECASE,
    )
    if fluence_section:
        result["fluence_15_150"] = float(fluence_section.group(1))

    return result


def format_swift_message(params: dict[str, any], trigger_id: int = None) -> Message:
    """
    Format the parsed parameters into a Slack message with proper header.

    Args:
        params: Dictionary returned by parse_swift_grb_html()
        trigger_id: Optional trigger ID to include source URL

    Returns:
        Message object with formatted alert information
    """
    msg = Message()

    # Add header
    msg.add_header("SWIFT BAT Detailed Analysis")
    msg.add_divider()

    lines = []

    if trigger_id:
        url = f"https://swift.gsfc.nasa.gov/results/BATbursts/{trigger_id}/bascript/top.html"
        lines.append(f"<{url}|HTLM source page>")
        lines.append("")

    # T90 duration (15-150 keV)
    if params["t90"] is not None:
        t90_str = f"{params['t90']:.2f}"
        if params["t90_error"] is not None:
            t90_str += f" ± {params['t90_error']:.2f}"
        lines.append(f"• *T90 (15-150 keV):* {t90_str} s")

    # T90 in BATSE band (50-300 keV)
    if params["t90_50_300"] is not None:
        lines.append(f"• *T90 (50-300 keV):* {params['t90_50_300']:.2f} s")

    # Hardness Ratio
    if params["hardness_ratio"] is not None:
        lines.append(f"• *Hardness ratio:* {params['hardness_ratio']:.2f}")

    # Fluence (15-150 keV)
    if params["fluence_15_150"] is not None:
        lines.append(
            f"• *Fluence (15-150 keV):* {params['fluence_15_150']:.3e} erg/cm²"
        )

    message_text = "\n".join(lines)
    msg.add_elements(BaseSection().add_text(MarkdownText(message_text)))

    return msg
