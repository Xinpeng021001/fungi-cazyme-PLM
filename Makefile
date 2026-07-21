PYTHON ?= $(if $(wildcard .venv/bin/python),.venv/bin/python,python)
PYTHONPATH ?= src
CONFIG ?= configs/data_sources.local.yaml

.PHONY: help install test phase0-smoke inventory import-aim2 gap labels structures report phase0

help:
	@echo "make install        Install package in current environment"
	@echo "make test           Run unit and integration tests"
	@echo "make phase0-smoke   Run deterministic fixture workflow"
	@echo "make phase0         Run the full CPU Phase 0 workflow"

install:
	$(PYTHON) -m pip install -e .

test:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m pytest

phase0-smoke:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m fungi_cazyme_plm.cli smoke --config tests/fixtures/config.yaml

inventory:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m fungi_cazyme_plm.cli inventory --config $(CONFIG)

import-aim2:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m fungi_cazyme_plm.cli import-aim2 --config $(CONFIG)

gap:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m fungi_cazyme_plm.cli phase0 gap --config $(CONFIG)

labels:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m fungi_cazyme_plm.cli phase0 labels --config $(CONFIG)

structures:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m fungi_cazyme_plm.cli phase0 structures --config $(CONFIG)

report:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m fungi_cazyme_plm.cli report phase0 --config $(CONFIG)

phase0:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m fungi_cazyme_plm.cli phase0 all --config $(CONFIG)
