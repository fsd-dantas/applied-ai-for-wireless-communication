"""Cross-component contracts and explicit capability gaps."""

from dataclasses import FrozenInstanceError

import pytest

from aisg.blackboard.network_sources import (
    DEGRADING_DIAGNOSES, IMPAIRING_DIAGNOSES, OUTAGE_DIAGNOSES,
)
from aisg.domain.diagnoses import (
    DIAGNOSES, EcoEffect, FaultMechanism, RoutingEffect, SimulationCapability,
    SimulationSupport, diagnosis_contract,
)
from aisg.domain.topology import load_topology
from aisg.eco.network import CONGESTED, DEGRADING, OUTAGE
from aisg.expert_system.kb_simulated import INDUCIBLE_BY, SIM_CASES
from aisg.planning.domain_restoration import (
    DIAGNOSIS_TO_FAULT, build_operators, cleared,
)
from aisg.simulation import ns3_scenario
from aisg.simulation.ns3_scenario import (
    FAULT_BY_DIAGNOSIS, ScenarioError, build_ns3_scenario,
)


def test_fixture_vocabulary_and_consumers_cover_the_same_diagnoses():
    """
    Read this one carefully: most of it cannot fail. INDUCIBLE_BY,
    DIAGNOSIS_TO_FAULT and every partition below are now DERIVED from DIAGNOSES by
    comprehension, so comparing them against DIAGNOSES compares a value with itself.
    That is a feature - drift is structurally impossible rather than merely tested -
    but it means the only genuinely independent check here is SIM_CASES, which is
    still hand-written in kb_simulated.py.

    The couplings that remain real are covered separately below: planner faults
    against the operators that clear them, and simulator mechanisms against the
    exporter branches that dispatch them.
    """
    assert set(DIAGNOSES) == set(SIM_CASES) == set(INDUCIBLE_BY) == set(DIAGNOSIS_TO_FAULT)
    routing_handled = set(IMPAIRING_DIAGNOSES) | set(DEGRADING_DIAGNOSES)
    eco_handled = set(OUTAGE) | set(DEGRADING) | set(CONGESTED)
    for name, contract in DIAGNOSES.items():
        assert (name in routing_handled) == (
            contract.routing_effect not in (RoutingEffect.NONE, RoutingEffect.UNSUPPORTED)
        )
        assert (name in eco_handled) == (
            contract.eco_effect not in (EcoEffect.NONE, EcoEffect.UNSUPPORTED)
        )
        assert (name in OUTAGE_DIAGNOSES) == contract.correlates_as_outage
        assert (name in FAULT_BY_DIAGNOSIS) == (
            contract.simulation.support in (
                SimulationSupport.SUPPORTED, SimulationSupport.APPROXIMATION
            )
        )


def test_healthy_baseline_is_not_an_unsupported_fault():
    healthy = diagnosis_contract("healthy")
    assert healthy.planner_fault is None
    assert healthy.routing_effect == RoutingEffect.NONE
    assert healthy.eco_effect == EcoEffect.NONE
    assert healthy.simulation.support == SimulationSupport.BASELINE
    assert "healthy" not in FAULT_BY_DIAGNOSIS
    assert all(c.planner_fault for name, c in DIAGNOSES.items() if name != "healthy")


def test_routing_fault_is_excluded_from_transit_though_no_simulator_induces_it():
    """
    The node answers but forwards nothing, so both decision components must refuse
    it as transit - EXCLUDE rather than AVOID_IF_POSSIBLE, because crossing it
    black-holes traffic instead of slowing it. Eco-resolution calls that degraded
    rather than down since the node is alive; `usable` forbids the path either way.

    Consumer handling and simulator injection are independent: the exporter still
    has no way to remove a route, and that gap is recorded on the capability, not
    as a `handling_gap` - which is reserved for consumers that ignore a diagnosis.
    """
    contract = diagnosis_contract("routing_misconfiguration")
    assert contract.planner_fault == "route-missing"
    assert contract.routing_effect == RoutingEffect.EXCLUDE
    assert contract.eco_effect == EcoEffect.DEGRADED
    assert not contract.handling_gap
    assert contract.simulation.support == SimulationSupport.UNSUPPORTED
    assert "routing_misconfiguration" in IMPAIRING_DIAGNOSES
    assert "routing_misconfiguration" in DEGRADING
    assert "routing_misconfiguration" not in FAULT_BY_DIAGNOSIS


def test_no_diagnosis_is_silently_ignored_by_a_consumer():
    """
    A diagnosis handled by neither component would be diagnosed correctly and then
    have no effect on any decision - the defect this contract exists to prevent.
    Only `healthy` may be absent from both partitions.
    """
    for name, contract in DIAGNOSES.items():
        handled = (
            contract.routing_effect != RoutingEffect.NONE
            or contract.eco_effect != EcoEffect.NONE
        )
        assert handled == (name != "healthy"), name
        if contract.routing_effect == RoutingEffect.UNSUPPORTED or (
            contract.eco_effect == EcoEffect.UNSUPPORTED
        ):
            assert contract.handling_gap, f"{name}: unsupported handling without an explanation"


def test_simulation_does_not_claim_distinct_radio_fault_mechanisms():
    for name in ("rf_interference", "excess_path_loss"):
        capability = diagnosis_contract(name).simulation
        assert capability.support == SimulationSupport.APPROXIMATION
        assert capability.mechanism == "radio_per"
    assert diagnosis_contract("mac_contention").simulation.support == SimulationSupport.UNSUPPORTED


def test_unknown_diagnosis_is_rejected():
    with pytest.raises(ValueError, match="Unknown diagnosis"):
        diagnosis_contract("route_typo")


def test_registry_and_contracts_cannot_be_mutated():
    with pytest.raises(TypeError):
        DIAGNOSES["new"] = DIAGNOSES["healthy"]
    with pytest.raises(FrozenInstanceError):
        DIAGNOSES["healthy"].planner_fault = "broken"


@pytest.mark.parametrize("support,mechanism", [
    (SimulationSupport.UNSUPPORTED, FaultMechanism.FLOOD),
    (SimulationSupport.BASELINE, FaultMechanism.NODE_DOWN),
    (SimulationSupport.SUPPORTED, None),
    (SimulationSupport.APPROXIMATION, None),
])
def test_inconsistent_simulation_capability_is_rejected(support, mechanism):
    with pytest.raises(ValueError, match="mechanism"):
        SimulationCapability(support, mechanism, "Explanation")


@pytest.mark.parametrize("mechanism", ["spectrum_jam", "node_down", "", 0, object()])
def test_non_enum_simulation_mechanisms_are_rejected(mechanism):
    with pytest.raises(ValueError, match="must be a FaultMechanism member or None"):
        SimulationCapability(SimulationSupport.SUPPORTED, mechanism, "Explanation")


def test_every_planner_fault_has_an_operator_that_clears_it():
    """
    Non-tautological, unlike the coverage check above. The contract names a repair
    literal per diagnosis; `build_operators()` hand-writes the operators. Nothing
    else ties the two together, and KNOWN_FAULTS is derived from the contract, so a
    contract entry naming a fault no operator produces would satisfy every other
    check here and then make the planning goal quietly unreachable.
    """
    for name, contract in DIAGNOSES.items():
        if contract.planner_fault is None:
            continue
        literal = cleared(contract.planner_fault)
        producers = [
            operator.name
            for operator in build_operators([contract.planner_fault])
            if any(str(predicate) == literal for predicate in operator.add_list)
        ]
        assert producers, f"{name}: no operator adds {literal}"


def test_a_mechanism_the_exporter_does_not_dispatch_is_refused(monkeypatch):
    """
    The other real coupling. `FaultMechanism` is closed, so a bogus string cannot
    reach a contract at all - but a member added there without a matching branch in
    `_add_faults` would previously export a scenario containing NO fault, silently,
    and that scenario would then be scored against predictions expecting one. The
    exporter must refuse rather than emit a fault-free run.
    """
    monkeypatch.setitem(ns3_scenario.FAULT_BY_DIAGNOSIS, "node_failure", "spectrum_jam")
    with pytest.raises(ScenarioError, match="not implemented by this exporter"):
        build_ns3_scenario(load_topology("dual"), fault_scenario="saf-chain-outage")


@pytest.mark.parametrize("mechanism", list(FaultMechanism))
def test_every_declared_mechanism_is_actually_dispatched(mechanism):
    """Exercise export and check fault targets, values, timing and rendered records.

    Enumerating the enum requires an executable case for each future mechanism,
    even before a diagnosis uses it. Expectations are independent of the registry.
    """
    cases = {
        FaultMechanism.NODE_DOWN: ("saf-chain-outage", "node_down", "SAF_02", "-"),
        FaultMechanism.RADIO_PER: ("independent-faults", "radio_per", "RM_07", "0.6"),
        FaultMechanism.FLOOD: ("independent-faults", "flood", "RELAY_5", "20Mbps"),
    }
    assert mechanism in cases, f"Add an exporter scenario for {mechanism}"
    scenario_name, kind, target, value = cases[mechanism]
    scenario = build_ns3_scenario(load_topology("dual"), fault_scenario=scenario_name)
    targets = {target}
    if mechanism == FaultMechanism.RADIO_PER:
        targets = {
            link.id for link in scenario.links
            if link.cls == "radio" and target in (link.a, link.b)
        }
        assert targets, "The test requires radio links at RM_07"
    expected = {(10.0, kind, fault_target, value) for fault_target in targets}
    actual = [fault for fault in scenario.faults if fault[1] == kind]
    assert set(actual) == expected
    assert len(actual) == len(expected)
    rendered = scenario.render().splitlines()
    for time, fault_kind, fault_target, fault_value in expected:
        assert f"fault {time:g} {fault_kind} {fault_target} {fault_value}" in rendered
