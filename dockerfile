FROM python:3.12-slim-bookworm AS base

ARG USR
ARG USR_GROUP
ARG PROJECT_UID
ARG PROJECT_GID

ENV GRANDMA_APP_HOME /home/${USR}/code

# Install OS libraries and add user specific to this project
RUN apt-get update \
 && apt-get install -y vim nano \
 && rm -rf /var/lib/apt/lists/* \
 && groupadd -g ${PROJECT_GID} ${USR_GROUP} \
 && useradd --create-home --no-log-init -u ${PROJECT_UID} -g ${PROJECT_GID} $USR \
 && install -d -m 0755 -o $USR -g $USR_GROUP $GRANDMA_APP_HOME

WORKDIR $GRANDMA_APP_HOME

RUN pip install --upgrade --no-cache-dir pip

RUN pip install pdm

COPY --chown=$USR:$USR_GROUP ./pyproject.toml .
COPY --chown=$USR:$USR_GROUP ./README.md .
COPY --chown=$USR:$USR_GROUP ./src ./src
COPY --chown=$USR:$USR_GROUP ./tests ./tests
COPY --chown=$USR:$USR_GROUP gcn_stream_config.toml .

# Switch to the user
USER $USR

RUN pdm build

RUN WHEEL_FILE=$(ls dist/*.whl) \
 && pip install --no-cache-dir $WHEEL_FILE
