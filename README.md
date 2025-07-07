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
from grandma_gcn.slackbot.gw_message import build_gwalert_data_msg

# Load a GW alert from a notice file
with open("path/to/notice.json", "rb") as fp:
    notice_bytes = fp.read()
gw_alert = GW_alert(notice_bytes, BBH_threshold=0.5, Distance_threshold=500, ErrorRegion_threshold=100)

# Build a Slack message
msg = build_gwalert_data_msg(gw_alert)
```

## Project Structure

- `src/grandma_gcn/gcn_stream/`: GW alert parsing, streaming, and logging
- `src/grandma_gcn/slackbot/`: Slack message formatting and bot integration
- `src/grandma_gcn/worker/`: Observation strategy generation, OwnCloud client, Celery tasks
- `tests/`: Unit and integration tests

## Docker & Docker Compose

The project provides two Docker Compose files: `compose_prod.yml` (for production) and `compose_test.yml` (for testing/E2E). These files allow you to deploy the application and its dependencies (PostgreSQL, Redis, Celery) in reproducible environments.

- **compose_prod.yml**: For production. Only mounts the necessary folders (`logs`, `catalogs`) and runs the main application (`gcn_stream`) with the production command.
- **compose_test.yml**: For tests and CI/E2E. Mounts the entire project source code into the container (`../grandma-gcn:/home/${USR}/code/`) and installs the package in editable mode (`pip install -e`). The main service (`gcn_stream`) uses a dummy command (`tail -F anything`) to allow test injection.
- Both files use an `init_volume` service to initialize permissions on shared volumes.
- Environment variables are centralized in the `.env` file at the project root.
- Docker volumes used:
  - `e2e_volume`: shared volume for temporary files and logs.
  - `pgdata` (test only): persistence for PostgreSQL data.

### Environment Variables

The `.env` file must contain all required variables, including:

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
POSTGRES_DB=grandma_db
POSTGRES_USER=user
POSTGRES_PASSWORD=pswd
POSTGRES_ROOT_PASSWORD=root
POSTGRES_PORT=1111
POSTGRES_HOST=db
SQLALCHEMY_DATABASE_URI=postgresql+psycopg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@${POSTGRES_HOST}:${POSTGRES_PORT}/${POSTGRES_DB}
```

- The `POSTGRES_*` variables are required for PostgreSQL configuration.
- Mount paths and permissions are managed via `USR`, `USR_GROUP`, `PROJECT_UID`, `PROJECT_GID`.

### Running the stack

For production:

```bash
docker compose -f compose_prod.yml build
docker compose -f compose_prod.yml up
```

For tests/E2E:

```bash
docker compose -f compose_test.yml build
docker compose -f compose_test.yml up
```

You can adjust environment variables in `.env` as needed.

## End-to-End (E2E) Testing

End-to-end tests are provided to simulate the full workflow (Kafka, Celery, Slack, etc.).

- Unit and integration tests are in the `tests/` directory.
- There are two types of E2E tests:
  - **Full E2E test** (`e2e`): Runs the complete processing pipeline, from GCN stream ingestion to Slack notification and observation plan generation. This test covers the integration of all main components and is the most comprehensive.
  - **Lighter E2E test** (`e2e_light`): Runs a reduced version of the pipeline, focusing on the GCN stream and Slack message posting, without triggering the full observation plan generation. This is useful for quickly checking the alert ingestion and notification logic.

To run all tests:

```bash
pytest
```

To run only the full E2E test:

```bash
pytest -m e2e
```

To run only the lighter E2E test:

```bash
pytest -m e2e_light
```

> **Note:** Make sure your TOML config files and `.env` are properly set up before running E2E tests. Some tests may require specific configuration or data files (see comments at the top of each test file for details).

## Testing

Run the test suite with:

```bash
pytest
```

## Configuration

- GW stream and OwnCloud credentials are configured via TOML files and environment variables.
- See example configuration files in the `tests/` directory.

## Database & Alembic Migrations

### Database

The project uses a **PostgreSQL** database managed with **SQLAlchemy**.

Currently, the main table is:

- `gw_alerts`: stores metadata about gravitational wave alerts, including:
  - `triggerId`: unique event ID
  - `thread_ts`: Slack thread timestamp
  - `reception_count`: number of times the alert was received

Database connections are initialized via the `init_db()` function:

```python
from grandma_gcn.database.db_utils import init_db

engine, SessionLocal = init_db(
    database_url="postgresql+psycopg://user:password@localhost:5432/grandma_db",
    echo=True
)
```

Then used like:

```python
from grandma_gcn.database.gw_db import GW_alert

with SessionLocal() as session:
    alerts = session.query(GW_alert).all()
```

You can inspect or modify alerts directly in PostgreSQL with:

```sql
-- List all alerts
SELECT * FROM gw_alerts;

-- Delete a specific alert
DELETE FROM gw_alerts WHERE "triggerId" = 'S241102br';
```

### 🛠 Alembic Migrations

**Alembic** is used to manage database schema migrations. Migration scripts live in:

```
src/alembic_migration/versions/
```

#### 📚 Creating a Migration

After modifying your SQLAlchemy models, generate a migration with:

```bash
alembic revision --autogenerate -m "your message here"
```

This creates a new file in `versions/`. Review and edit it before applying.

#### 🚀 Applying Migrations

To apply all pending migrations:

```bash
alembic upgrade head
```

To apply a specific migration:

```bash
alembic upgrade <revision_id>
```

#### ⬅️ Rolling Back

To undo the latest migration:

```bash
alembic downgrade -1
```

Or to a specific revision:

```bash
alembic downgrade <revision_id>
```

#### ⚙️ Alembic Setup

If not already configured, generate an Alembic environment with:

```bash
alembic init src/alembic_migration
```

Then in `alembic.ini`, set:

```
script_location = src/alembic_migration
```

And in `env.py`, update your target metadata and engine import:

```python
from grandma_gcn.database.db_base import Base
target_metadata = Base.metadata
```

You can also import your models to ensure they are registered.

#### 🧪 Troubleshooting

If Alembic fails with errors like:

```
sqlalchemy.exc.ProgrammingError: (psycopg.errors.UndefinedTable) relation "gw_alerts" does not exist
```

This likely means:
- The initial migration was not applied.
- The table was dropped or the DB was reset.

Fix it with:

```bash
alembic upgrade head
```

Or recreate from scratch if needed.

---

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
      ├───────────────► Slack Notification (alert received & significant)
      │
      ▼
Save Notice & Log
      │
      ├───────────────► OwnCloud Folder Creation
      │
      ├───────────────► Slack Notification (inform GWEMOPT starting)
      │
      ▼
Trigger GWEMOPT (Celery)
      │
      ▼
Upload Results to OwnCloud
      │
      ├───────────────► Slack Notification (GWEMOPT results ready)
      │
      ▼
End of Pipeline
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
