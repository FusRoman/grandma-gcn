# grandma-gcn

![Tests](https://github.com/FusRoman/grandma-gcn/actions/workflows/tests.yml/badge.svg)
[![codecov](https://codecov.io/gh/FusRoman/grandma-gcn/branch/main/graph/badge.svg)](https://codecov.io/gh/FusRoman/grandma-gcn)

## Overview

**grandma-gcn** is a Python package for processing, analyzing, and distributing gravitational wave (GW) alerts, designed for the GRANDMA collaboration. It provides tools to parse GW notices, generate observation strategies, and automate notifications and data sharing.

## Features

- Parse and handle GW alerts (GCN, GraceDB, etc.)
- Generate observation strategies using [gwemopt](https://github.com/FusRoman/old_gwemopt)
- Slack bot integration for real-time notifications
- OwnCloud integration for sharing data products
- Utilities for managing GW event data and links (SkyPortal, GraceDB, etc.)
- Comprehensive test suite

## Installation

Clone the repository and install dependencies (Python 3.12+ required):

```bash
git clone https://github.com/FusRoman/grandma-gcn.git
cd grandma-gcn
pdm install -G :all
```

## Usage

The package is modular and can be used as a library or as part of automated pipelines.

Example: Load and process a GW alert

```python
from grandma_gcn.gcn_stream.gw_alert import GW_alert
from grandma_gcn.slackbot.gw_message import build_gwalert_msg

# Load a GW alert from a notice file
with open("path/to/notice.json", "rb") as fp:
    notice_bytes = fp.read()
gw_alert = GW_alert(notice_bytes, BBH_threshold=0.5, Distance_threshold=500, ErrorRegion_threshold=100)

# Build a Slack message
msg = build_gwalert_msg(gw_alert)
```

## Project Structure

- `src/grandma_gcn/gcn_stream/`: GW alert parsing, streaming, and logging
- `src/grandma_gcn/slackbot/`: Slack message formatting and bot integration
- `src/grandma_gcn/worker/`: Observation strategy generation, OwnCloud client, Celery tasks
- `tests/`: Unit and integration tests

## Testing

Run the test suite with:

```bash
pytest
```

## Configuration

- GW stream and OwnCloud credentials are configured via TOML files and environment variables.
- See example configuration files in the `tests/` directory.

## Contributing

Contributions are welcome! Please open issues or pull requests on [GitHub](https://github.com/FusRoman/grandma-gcn).

## License

Distributed under the CeCILL-C License. See [LICENSE](LICENSE) for details.

## Acknowledgments

Developed as part of the GRANDMA collaboration.
