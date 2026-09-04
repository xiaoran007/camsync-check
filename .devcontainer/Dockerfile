FROM mcr.microsoft.com/devcontainers/base:1-bookworm@sha256:ce2e9e611939e611b737362c045bb6d3449bb3efb84898525d724aace1737b90

USER root
RUN apt-get update \
    && apt-get install --yes --no-install-recommends python3-venv make \
    && rm -rf /var/lib/apt/lists/* \
    && python3 -m venv /opt/platformio \
    && /opt/platformio/bin/pip install --no-cache-dir platformio==6.1.18

ENV PATH="/opt/platformio/bin:${PATH}"
USER vscode
WORKDIR /workspace
