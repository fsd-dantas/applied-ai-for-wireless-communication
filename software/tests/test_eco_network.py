"""
Tests for eco-resolution on the dual-homed backhaul.

PT-BR: Propriedades verificadas: prioridade (nenhum fluxo agride outro de
       prioridade igual ou maior), coerencia do resultado (todo fluxo satisfeito
       esta num meio utilizavel e dentro da capacidade), dependencia (telemetria
       nunca satisfeita antes do SCADA do proprio site) e o comportamento em cada
       cenario de falha do quadro-negro.
EN:    Properties checked: priority (no flow attacks one of equal or higher
       priority), outcome coherence (every satisfied flow is on a usable medium
       and within capacity), dependency (telemetry never satisfied before its own
       site's SCADA flow) and the behaviour in each blackboard fault scenario.
"""

from __future__ import annotations

import pytest

from aisg.domain import load_topology
from aisg.eco import PARKED, network_ecosystem


@pytest.fixture(scope="module")
def topology():
    return load_topology("dual")


@pytest.fixture(scope="module")
def solved(topology):
    results = {}
    for scenario in (None, "saf-chain-outage", "dual-outage", "independent-faults"):
        problem = network_ecosystem(topology, scenario)
        results[scenario] = (problem, problem.ecosystem.solve())
    return results


def priority(flow: str) -> int:
    return 2 if flow.endswith("/scada") else 1


def test_without_a_fault_every_flow_is_already_satisfied(solved):
    problem, result = solved[None]
    assert result.converged and result.moves == []
    assert len(problem.world.flows) == 30


@pytest.mark.parametrize("scenario", ["saf-chain-outage", "dual-outage", "independent-faults"])
def test_no_flow_attacks_an_equal_or_higher_priority_flow(solved, scenario):
    _problem, result = solved[scenario]
    for entry in result.trace:
        if entry.event == "attack":
            victim = entry.detail.split(" blocks ")[0]
            assert priority(victim) < priority(entry.agent), entry.render("en")


@pytest.mark.parametrize("scenario", [None, "saf-chain-outage", "dual-outage", "independent-faults"])
def test_satisfied_flows_are_on_usable_media_within_capacity(solved, scenario):
    problem, result = solved[scenario]
    world = problem.world
    unsatisfied = set(result.unsatisfied)
    for resource, capacity in world.capacities.items():
        assert len([o for o in world.occupants(resource) if o not in unsatisfied]) <= capacity
    for name, medium in world.assignment.items():
        if name not in unsatisfied:
            assert medium != PARKED
            assert world.usable(world.flows[name].site, medium)


@pytest.mark.parametrize("scenario", ["saf-chain-outage", "dual-outage", "independent-faults"])
def test_telemetry_is_never_satisfied_without_its_sites_scada(solved, scenario):
    _problem, result = solved[scenario]
    unsatisfied = set(result.unsatisfied)
    for flow in unsatisfied:
        if flow.endswith("/scada"):
            assert flow.replace("/scada", "/telemetry") in unsatisfied


def test_a_relay_outage_restores_scada_by_displacing_telemetry(solved):
    """
    SAF_02 takes ER_06's 900 MHz path. RELAY_5's cell is already full, so
    ER_06's SCADA flow attacks the weakest occupant - ER_07's telemetry, whose
    own 900 MHz path also crosses SAF_02, so it can only park. ER_06's
    telemetry cannot displace an equal and stays unserved.
    """
    problem, result = solved["saf-chain-outage"]
    a = problem.world.assignment
    assert a["ER_06/scada"] == "plte"
    attacks = [(e.agent, e.detail.split(" blocks ")[0]) for e in result.trace if e.event == "attack"]
    assert attacks == [("ER_06/scada", "ER_07/telemetry")]
    assert a["ER_07/telemetry"] == "parked"
    assert set(result.unsatisfied) == {"ER_06/telemetry", "ER_07/telemetry"}
    assert not result.converged
    moved = {m.agent for m in result.moves}
    assert moved == {"ER_06/scada", "ER_07/telemetry"}


def test_isolated_sites_stay_unsatisfied_and_nothing_else_moves(solved):
    """Only repair restores a site with both media down; the agents say so."""
    problem, result = solved["dual-outage"]
    assert not result.converged
    isolated = {"ER_03", "ER_04", "ER_06", "ER_07"}
    assert {f.split("/")[0] for f in result.unsatisfied} == isolated
    for flow, medium in problem.world.assignment.items():
        if flow.split("/")[0] not in isolated:
            assert medium == problem.initial[flow]


def test_congestion_sheds_telemetry_before_scada(solved):
    """
    RELAY_5's cell drops to two flows. SCADA keeps the cell, telemetry moves to
    a clean 900 MHz path, and ER_07 - whose 900 MHz path crosses the degraded
    RM_07 - cannot be served at all.
    """
    problem, result = solved["independent-faults"]
    a = problem.world.assignment
    assert problem.congested == {"RELAY_5"} and "RM_07" in problem.degraded
    assert a["ER_03/scada"] == "plte" and a["ER_04/scada"] == "plte"
    assert a["ER_03/telemetry"] == "radio900" and a["ER_04/telemetry"] == "radio900"
    assert "ER_07/scada" in result.unsatisfied
    # SCADA already ranks ahead within the reduced capacity, so telemetry
    # yields by moving - no aggression is needed, and only telemetry moves.
    assert {m.agent for m in result.moves} == {"ER_03/telemetry", "ER_04/telemetry"}


def test_a_misconfigured_route_makes_every_path_across_it_unusable(topology, monkeypatch):
    """
    The eco half of the same gap. SAF_02 answers but forwards nothing, so no flow
    may keep a 900 MHz path crossing it. It is recorded as degraded rather than
    down because the node is alive; `usable` forbids the path either way.

    The scenario is registered for this test only - the three published fault
    scenarios stay three, since the ns-3 exporter cannot induce this fault.
    """
    from aisg.blackboard import scenarios

    def misconfigured(topo):
        observed = sorted(
            n.id for n in topo.nodes.values() if n.kind in scenarios.OBSERVED_KINDS
        )
        return scenarios.Scenario(
            "route-misconfig",
            "Rota ausente em SAF_02", "Missing route at SAF_02",
            observations=[
                scenarios.observation_for(
                    node,
                    "routing_misconfiguration" if node == "SAF_02" else "healthy",
                    "route-misconfig",
                )
                for node in observed
            ],
            commanded={"SAF_02": "routing_misconfiguration"},
        )

    monkeypatch.setitem(scenarios.SCENARIOS, "route-misconfig", misconfigured)
    problem = network_ecosystem(topology, "route-misconfig")

    assert problem.degraded == {"SAF_02"}
    assert problem.down == frozenset() and problem.congested == frozenset()
    crossing = [
        site for site, media in problem.world.sites.items()
        if "SAF_02" in media.path_nodes["radio900"]
    ]
    assert crossing, "no 900 MHz path crosses SAF_02, so the case proves nothing"
    for site in crossing:
        assert not problem.world.usable(site, "radio900"), site


def test_the_world_state_comes_from_the_blackboards_diagnosis(solved):
    assert solved["saf-chain-outage"][0].down == {"SAF_02"}
    assert solved["dual-outage"][0].down == {"SAF_02", "RELAY_5"}
