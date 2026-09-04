SHELL := /bin/sh
.DEFAULT_GOAL := help

DOCKER ?= docker
BOARD ?= uno_r4_wifi
COMPOSE = $(DOCKER) compose -f "$(CURDIR)/.devcontainer/compose.yaml"
RUN = $(COMPOSE) run --rm --no-deps --user "$$(id -u):$$(id -g)" firmware

.PHONY: help image dev firmware

help:
	@printf '%s\n' \
	  'make image                  Build the firmware environment' \
	  'make dev                    Open a shell in that environment' \
	  'make firmware [BOARD=...]   Compile firmware inside the container'

image:
	$(COMPOSE) build firmware

dev: image
	$(RUN) bash

firmware: image
	$(RUN) pio run -d firmware -e "$(BOARD)"
