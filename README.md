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

## Docker & Docker Compose

The project includes a `Dockerfile` and a `docker-compose.yml` for easy deployment and reproducible environments.

- **Dockerfile**: Builds an image with all dependencies and the grandma-gcn codebase.
- **docker-compose.yml**: Provides services for the main app, Redis (for Celery), and other dependencies. It is recommended for local development and testing.

To build and run the stack:

```bash
docker compose build
docker compose up
```

You can customize environment variables (e.g., Slack token, Redis host, OwnCloud credentials) in the `.env` file at the project root.

### Example `.env` file

The `.env` file is used to configure environment variables for Docker Compose and Celery. Here is an example of the required variables:

```env
FINK_SLACK_TOKEN=your-slack-token-here

USR=grandma_gcn
USR_GROUP=grandma
PROJECT_GID=1000
PROJECT_UID=1000

REDIS_HOST=redis
REDIS_PORT=6379
CELERY_BROKER_URL=redis://${REDIS_HOST}:${REDIS_PORT}/0
CELERY_RESULT_BACKEND=redis://${REDIS_HOST}:${REDIS_PORT}/0
```

- `FINK_SLACK_TOKEN`: Slack bot token for posting messages.
- `CELERY_BROKER_URL` and `CELERY_RESULT_BACKEND`: URLs for the Redis instance used by Celery.
- User and group variables are used for permissions inside the container.

## End-to-End (E2E) Testing

An end-to-end test is provided in [`tests/test_e2e.py`](tests/test_e2e.py) to simulate the full workflow, including:

- Mocking Kafka GCN messages
- Processing and saving GW notices
- Verifying Celery post-processing tasks

### Required TOML configuration

To run the E2E test, you need a TOML configuration file (for example, `gcn_stream_config.toml`) with the following required sections and secrets.

```toml
[CLIENT]
id = "your-kafka-client-id"
secret = "your-kafka-client-secret"

[KAFKA_CONFIG]
"group.id" = "test_e2e"
"auto.offset.reset" = "earliest"
"enable.auto.commit" = false

[GCN_TOPICS]
topics = ["igwn.gwalert"]

[PATH]
gcn_stream_log_path = "gcn_stream_e2e.log"
notice_path = "notices"
celery_task_log_path = "gwemopt_task"

[THRESHOLD]
BBH_proba = 0.5        # between 0 and 1
Distance_cut = 5000    # in Mpc
BNS_NSBH_size_cut = 5000 # in deg²
BBH_size_cut = 5000 # in deg²

[Slack]
gw_alert_channel = "#your_slack_channel"
gw_alert_channel_id = "your_slack_channel_id"

[GWEMOPT]
# You can specify several independent GWEMOPT tasks by providing lists of lists.
# Each sublist corresponds to a separate GWEMOPT task (e.g., for different telescope groups or strategies).
telescopes = [["TCH", "TRE"], ["TCA", "FZU-CTA-N"], ["FZU-Auger", "UBAI-T60S"], ["KAO", "Colibri"]]
number_of_tiles = [[10, 10], [10, 15], [15, 10], [10, 10]]
observation_strategy = ["Tiling", "Tiling", "Galaxy targeting", "Galaxy targeting"]
nside_flat = 512
path_galaxy_catalog = "catalogs/"
galaxy_catalog = "mangrove"

[OWNCLOUD]
username = "your_owncloud_username"
password = "your_owncloud_password"
base_url = "https://your-owncloud-instance/remote.php/dav/files/your_owncloud_username/"
```

**Required secrets and credentials:**
- Kafka client `id` and `secret` for GCN stream access.
- Slack bot token (`FINK_SLACK_TOKEN` in `.env`), channel name, and channel ID.
- OwnCloud username, password, and WebDAV base URL.

#### Notes on GWEMOPT configuration

- The `[GWEMOPT]` section supports launching multiple independent GWEMOPT tasks in parallel.
- Each entry in `telescopes`, `number_of_tiles`, and `observation_strategy` must be a list of the same length, where each sublist or value defines the configuration for one GWEMOPT task.
- For example, the first GWEMOPT task will use telescopes `["TCH", "TRE"]` with `[10, 10]` tiles and `"Tiling"` strategy, the second task will use `["TCA", "FZU-CTA-N"]` with `[10, 15]` tiles and `"Tiling"` strategy, etc.

#### Notes on thresholds and GW_alert usage

- The `[THRESHOLD]` section replaces the old `[Threshold]` and now uses explicit keys: `BBH_proba`, `Distance_cut`, `BNS_NSBH_size_cut`, `BBH_size_cut`.
- When creating a `GW_alert` object, you should now pass the thresholds as a dictionary, for example:

```python
gw_alert = GW_alert(
    notice_bytes,
    thresholds={
        "BBH_proba": 0.5,
        "Distance_cut": 500,
        "BNS_NSBH_size_cut": 100,
        "BBH_size_cut": 100,
    }
)
```

### Running the E2E test

Once your `.env` and TOML config files are set up, run:

```bash
pytest -m e2e
```

This will execute the end-to-end workflow, including message ingestion, processing, and post-processing via Celery.

## Testing

Run the test suite with:

```bash
pytest
```

## Configuration

- GW stream and OwnCloud credentials are configured via TOML files and environment variables.
- See example configuration files in the `tests/` directory.

## Alert Processing Pipeline

The grandma-gcn package implements a modular and automated pipeline for handling gravitational wave (GW) alerts from ingestion to dissemination. Here is a detailed overview of the main steps:

1. **Alert Ingestion (GCN over Kafka):**
   - The pipeline listens to real-time GW alerts distributed via [NASA GCN over Kafka](https://gcn.nasa.gov/kafka/).
   - Alerts are consumed from the Kafka stream using the configured client credentials.

2. **Alert Parsing and Filtering:**
   - Each alert (notice) is parsed and converted from bytes to a Python dictionary.
   - The alert is encapsulated in a `GW_alert` object, which extracts key event information (event ID, type, time, classification, FAR, etc.).
   - The alert is scored and filtered based on configurable thresholds (e.g., BBH probability, distance, error region size) to determine its significance.

3. **Persistence and Logging:**
   - Significant alerts are saved as JSON files in the configured notice directory.
   - All processing steps and decisions are logged for traceability.

4. **OwnCloud Integration:**
   - For each alert, a dedicated folder structure is created on OwnCloud to store data products, images, logbooks, and VOEvents.
   - GWEMOPT results and plots are automatically uploaded to the corresponding OwnCloud directories.

5. **Observation Strategy Generation (GWEMOPT):**
   - The pipeline triggers one or more Celery tasks to generate observation strategies using [gwemopt](https://github.com/FusRoman/old_gwemopt).
   - Both "tiling" and "galaxy targeting" strategies can be computed, depending on the event and configuration.
   - The results include sky maps, tile lists, and coverage plots.

6. **Slack Notification:**
   - A Slack bot posts a detailed message to the configured channel, summarizing the alert and providing links to relevant resources (SkyPortal, GraceDB, OwnCloud).
   - When GWEMOPT processing is complete, a follow-up message is posted with coverage maps and execution details.

7. **Automated Cleanup and Post-processing:**
   - After successful processing, notices and temporary files are cleaned up as needed.
   - The pipeline is designed to be robust and can be run continuously as a service.

**Summary Diagram:**

```
GCN Kafka Stream
      │
      ▼
Alert Ingestion & Parsing
      │
      ▼
Significance Filtering ──► (discard if not significant)
      │
      ▼
Save Notice & Log
      │
      ├───────────────► OwnCloud Folder Creation
      │
      ▼
Trigger GWEMOPT (Celery)
      │
      ▼
Upload Results to OwnCloud
      │
      ▼
Slack Notification
```

This pipeline ensures that GW alerts are processed rapidly, observation strategies are generated and distributed, and all relevant stakeholders are notified in real time.

## About NASA GCN

This project is built around the [NASA Gamma-ray Coordinates Network (GCN)](https://gcn.nasa.gov/), which is a real-time system for distributing alerts and notices about astrophysical transients such as gamma-ray bursts (GRBs), gravitational wave events, and other multi-messenger phenomena.

The new generation of GCN, known as **GCN over Kafka**, uses the [Apache Kafka](https://kafka.apache.org/) protocol to provide a scalable, robust, and low-latency message streaming service for astronomical alerts. This allows observatories and astronomers to subscribe to real-time streams of transient event notifications, enabling rapid follow-up and coordination across the global community. The grandma-gcn package is designed to interface directly with GCN over Kafka, making it easy to consume, process, and react to gravitational wave alerts as soon as they are published.

## Contributing

Contributions are welcome! Please open issues or pull requests on [GitHub](https://github.com/FusRoman/grandma-gcn).

## License

Distributed under the CeCILL-C License. See [LICENSE](LICENSE) for details.

## Acknowledgments

Developed as part of the GRANDMA collaboration.
