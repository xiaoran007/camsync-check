FROM mcr.microsoft.com/devcontainers/base:1-bookworm

USER root
RUN apt-get update \
    && apt-get install --yes --no-install-recommends python3-venv make \
    && rm -rf /var/lib/apt/lists/* \
    && python3 -m venv /opt/platformio \
    && /opt/platformio/bin/pip install --no-cache-dir platformio==6.1.18

ENV PATH="/opt/platformio/bin:${PATH}"
USER vscode
WORKDIR /workspace
