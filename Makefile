PYTHON ?= python

.PHONY: install test cli-smoke check

install:
	$(PYTHON) -m pip install -e ".[dev]"

test:
	$(PYTHON) -m pytest

cli-smoke:
	aisg --version
	aisg --lang en diagnose --case rf_interference
	aisg --lang en route --compare
	aisg --lang en pipeline --case congestion
	aisg --lang en blackboard --scenario dual-outage
	aisg --lang en eco --problem blocks
	aisg --lang en eco --problem network --scenario saf-chain-outage
	aisg --lang en ns3-diagnose --results experiments/004-multi-rat-simulation/results/saf-chain-outage/none --fault-scenario saf-chain-outage

check: test cli-smoke
