SHELL := /bin/sh
.DEFAULT_GOAL := help

DOCKER ?= docker
BOARD ?= uno_r4_wifi
PORT ?=
ARDUINO_CLI ?= arduino-cli
export BOARD PORT ARDUINO_CLI
COMPOSE = $(DOCKER) compose -f "$(CURDIR)/.devcontainer/compose.yaml"
RUN = $(COMPOSE) run --rm --no-deps --user "$$(id -u):$$(id -g)" firmware

.PHONY: help image dev firmware ports upload monitor test

help:
	@printf '%s\n' \
	  'make image                  Build the firmware environment' \
	  'make dev                    Open a shell in that environment' \
	  'make firmware [BOARD=...]   Compile firmware inside the container' \
	  'make ports                  List connected boards on the host' \
	  'make upload PORT=...        Upload the existing firmware from the host' \
	  'make monitor PORT=...       Open the host serial monitor at 115200 baud' \
	  'make test                   Run the automated Python test suite'

image:
	$(COMPOSE) build firmware

dev: image
	$(RUN) bash

firmware: image
	$(RUN) pio run -d firmware -e "$(BOARD)"

ports upload monitor:
	@.venv/bin/python scripts/board.py $@

test:
	.venv/bin/python -m unittest discover -s tests -v
