"""
Tests for the multi-expert blackboard.

PT-BR: Tres familias de propriedades. (1) EQUIVALENCIA: dividir a base em
       especialistas nao muda nenhuma conclusao sobre um no isolado. (2) GANHO: o
       que so a visao de rede permite - uma causa comum para muitas interrupcoes,
       sem fundir falhas independentes. (3) CONTROLE: o laco chega a quiescencia,
       e toda entrada do quadro tem autor e suporte.

       Os conjuntos esperados foram lidos da topologia a mao e ficam escritos no
       teste, e nao calculados pelo codigo verificado.

EN:    Three families of properties. (1) EQUIVALENCE: splitting the base into
       experts changes no conclusion about a single node. (2) GAIN: what only the
       network view allows - one common cause for many outages, without merging
       independent faults. (3) CONTROL: the loop reaches quiescence, and every entry
       on the board has an author and support.

       The expected sets were read off the topology by hand and are written in the
       test, not computed by the code under test.
"""

from __future__ import annotations

import pytest

from aisg.blackboard import (
    EXPERT_SPECS,
    SCENARIOS,
    TASK_GENERATOR,
    AccessRouter,
    Blackboard,
    Controller,
    Entry,
    Level,
    MultiRatArbiter,
    TaskGenerator,
    build_experts,
    build_rule_experts,
    build_scenario,
    solve,
    unreachable_without,
)
from aisg.domain import load_topology
from aisg.expert_system import (
    FIRING_THRESHOLD,
    SIM_CASES,
    InferenceEngine,
    build_simulated_knowledge_base,
)
from aisg.observation import Observation

#: Downstream of SAF_02 in the 60-node scenario, read off the link list.
SAF_02_DOWNSTREAM = {
    "SAF_03", "SAF_04", "SAF_05", "SAF_06",
    "RM_01", "RM_02", "RM_03", "RM_04", "RM_06", "RM_07",
    "RM_09", "RM_11", "RM_12", "RM_13", "RM_14", "RM_15",
}
#: Sites whose remote radio hangs below SAF_02.
SAF_02_SITES = {
    "ER_01", "ER_02", "ER_03", "ER_04", "ER_06", "ER_07",
    "ER_09", "ER_11", "ER_12", "ER_13", "ER_14", "ER_15",
}
#: Sites served by RELAY_5 over private LTE - and, with SAF_02 down, by nothing.
RELAY_5_SITES = {"ER_03", "ER_04", "ER_06", "ER_07"}


@pytest.fixture(scope="module")
def topology():
    return load_topology("dual")


@pytest.fixture(scope="module")
def runs(topology):
    return {name: solve(build_scenario(name, topology), topology) for name in SCENARIOS}


# -- (1) equivalence ---------------------------------------------------------
def test_every_rule_belongs_to_exactly_one_expert():
    assigned = [rule_id for spec in EXPERT_SPECS for rule_id in spec[5]]
    assert len(assigned) == len(set(assigned)), "a rule is assigned twice"
    assert set(assigned) == {r.id for r in build_simulated_knowledge_base().rules}


def test_each_expert_is_a_consistent_base_on_its_own():
    for expert in build_rule_experts():
        assert expert.kb.validate() == [], expert.name
        assert expert.writes, f"{expert.name} writes nothing"


def _single_node_board(case: str) -> Blackboard:
    board = Blackboard()
    observation = Observation(
        subject_id="X", values={k: (v, 1.0) for k, v in SIM_CASES[case].items()}
    )
    TaskGenerator(board).post([observation])
    Controller(board, build_rule_experts()).loop()
    return board


@pytest.mark.parametrize("case", sorted(SIM_CASES))
def test_splitting_the_base_changes_no_conclusion(case):
    """
    The blackboard must reach, for one node, exactly what the single knowledge
    base reaches: same values, same certainty factors, for every goal.
    """
    engine = InferenceEngine(build_simulated_knowledge_base())
    for variable, value in SIM_CASES[case].items():
        engine.given(variable, value)
    engine.forward_chain()
    board = _single_node_board(case)

    for goal in ("diagnosis", "recommended_action", "authorization_required"):
        single = [(f.value, round(f.cf, 9)) for f in engine.memory.ranked(goal, min_cf=FIRING_THRESHOLD)]
        multi = [(v, round(cf, 9)) for v, cf in board.ranked(
            Level.HYPOTHESIS, "X", goal, min_cf=FIRING_THRESHOLD)]
        assert multi == single, f"{case}/{goal}"


# -- (2) what the network view adds ------------------------------------------
def test_scenario_ground_truth_is_independent_reachability(topology):
    assert unreachable_without(topology, ["SAF_02"]) == SAF_02_DOWNSTREAM


def test_one_relay_down_is_one_incident_not_sixteen(runs):
    incidents = runs["saf-chain-outage"].board.entries(Level.INCIDENT)
    assert len(incidents) == 1
    (incident,) = incidents
    assert (incident.subject, incident.value) == ("SAF_02", "node_failure")
    assert incident.data["kind"] == "correlated"
    assert set(incident.data["explains"]) == SAF_02_DOWNSTREAM


def test_two_simultaneous_causes_are_kept_apart(runs):
    incidents = runs["dual-outage"].board.entries(Level.INCIDENT)
    roots = {(e.subject, e.value, e.data["kind"]) for e in incidents}
    assert roots == {
        ("SAF_02", "node_failure", "correlated"),
        ("RELAY_5", "node_failure", "correlated"),
    }


def test_independent_faults_are_never_merged(runs):
    incidents = runs["independent-faults"].board.entries(Level.INCIDENT)
    assert {e.data["kind"] for e in incidents} == {"local"}
    assert {(e.subject, e.value) for e in incidents} == {
        ("RM_07", "rf_interference"),
        ("RELAY_5", "congestion"),
    }


def test_a_healthy_node_is_never_blamed(runs):
    board = runs["dual-outage"].board
    for incident in board.entries(Level.INCIDENT):
        best = board.best(Level.HYPOTHESIS, incident.subject, "diagnosis")
        assert best is None or best[0] != "healthy", incident.subject


def test_losing_the_900mhz_chain_moves_every_site_to_private_lte(runs):
    board = runs["saf-chain-outage"].board
    routes = {e.subject: e for e in board.entries(Level.ACCESS, key="route")}
    assert set(routes) == SAF_02_SITES
    for site, route in routes.items():
        assert route.value == "restored", site
        assert route.data["medium"] == "plte", site
        assert "SAF_02" not in route.data["path"], site
    decisions = {e.value for e in board.entries(Level.ACCESS, key="decision")}
    assert "isolated" not in decisions


def test_losing_both_media_isolates_exactly_the_shared_sites(runs):
    board = runs["dual-outage"].board
    isolated = {
        e.subject for e in board.entries(Level.ACCESS, key="decision")
        if e.value == "isolated"
    }
    assert isolated == RELAY_5_SITES


def test_restored_routes_are_real_paths_avoiding_every_impaired_node(runs, topology):
    for name, run in runs.items():
        impaired = {e.subject for e in run.board.entries(Level.INCIDENT)
                    if e.value in ("node_failure", "upstream_relay_failure", "congestion")}
        for route in run.board.entries(Level.ACCESS, key="route"):
            path = route.data["path"]
            if route.value != "restored":
                continue
            assert not impaired & set(path), f"{name}: {route.subject} crosses {impaired & set(path)}"
            for u, v in zip(path, path[1:]):
                assert any(nb == v for nb, _ in topology.neighbours(u)), f"{u}-{v} is not a link"


def test_a_degraded_node_is_avoided_when_possible_and_flagged_when_not(runs):
    """
    With RELAY_5 congested, ER_07's only remaining medium runs through RM_07,
    which the RF expert found interfered. No clean route exists, so the route
    stays and says so. ER_03 and ER_04 reach 900 MHz without touching RM_07.
    """
    board = runs["independent-faults"].board
    routes = {e.subject: e for e in board.entries(Level.ACCESS, key="route")}
    assert routes["ER_07"].data["crosses_degraded"] == ["RM_07"]
    assert routes["ER_03"].data["crosses_degraded"] == []
    assert routes["ER_04"].data["crosses_degraded"] == []
    decision = board.entries(Level.ACCESS, subject="ER_07", key="decision")[0]
    assert decision.data["degraded_via"] == ["RM_07"]


def test_congestion_is_not_traded_for_a_degraded_path(runs):
    """
    Found in simulation: moving ER_07 off congested LTE onto the interfered
    RM_07 raised its loss from 14% to 57%. A congested medium still works, so the
    site holds it; sites whose alternative is clean still switch.
    """
    board = runs["independent-faults"].board
    decisions = {e.subject: e for e in board.entries(Level.ACCESS, key="decision")}
    assert decisions["ER_07"].value == "hold"
    assert decisions["ER_07"].data["stay_on"] == "plte"
    assert decisions["ER_03"].value == "switch_medium"
    assert decisions["ER_04"].value == "switch_medium"
    # an outage is never held, even when the alternative is degraded
    for run in (runs["saf-chain-outage"], runs["dual-outage"]):
        assert "hold" not in {e.value for e in run.board.entries(Level.ACCESS, key="decision")}
    for route in runs["saf-chain-outage"].board.entries(Level.ACCESS, key="route"):
        assert route.data["crosses_degraded"] == []


# -- a node that answers but forwards nothing --------------------------------
def _rerouted(topology, *misconfigured: str) -> Blackboard:
    """
    Run only the router and the arbiter over hand-placed incidents.

    Skipping the rule experts keeps the two cases below about one question - is a
    node diagnosed `routing_misconfiguration` still used as transit - rather than
    about which observations make S19 fire, which the equivalence tests cover.
    """
    board = Blackboard()
    board.publish(
        "correlator",
        [
            Entry(Level.INCIDENT, node, "incident", "routing_misconfiguration", 1.0,
                  "correlator", (f"{node}:routing_misconfiguration",),
                  data={"kind": "local", "explains": [], "observed": True, "depth": 0})
            for node in misconfigured
        ],
        levels=(Level.INCIDENT,),
    )
    Controller(board, [AccessRouter(topology), MultiRatArbiter()]).loop()
    return board


def test_a_misconfigured_route_is_avoided_when_an_alternative_exists(topology):
    """
    SAF_02 answers, so no rule calls it stopped - but it forwards nothing, and
    routing it through anyway black-holes the traffic. The expected sets are the
    outage ones above: the correlator reduces `saf-chain-outage` to this same
    single incident, so avoiding a misconfigured node must reroute identically.
    """
    board = _rerouted(topology, "SAF_02")
    routes = {e.subject: e for e in board.entries(Level.ACCESS, key="route")}
    assert set(routes) == SAF_02_SITES
    for site, route in routes.items():
        assert route.value == "restored", site
        assert route.data["medium"] == "plte", site
        assert "SAF_02" not in route.data["path"], site
        assert route.data["blocker_diagnoses"]["SAF_02"] == "routing_misconfiguration"
    assert "isolated" not in {e.value for e in board.entries(Level.ACCESS, key="decision")}


def test_a_misconfigured_route_with_no_alternative_isolates_the_site(topology):
    """
    The no-route half. Both media black-holed leaves the same four sites with
    nowhere to go as `dual-outage` does, and the arbiter must say isolated rather
    than hand back a route across a node that will not forward.
    """
    board = _rerouted(topology, "SAF_02", "RELAY_5")
    decisions = {e.subject: e for e in board.entries(Level.ACCESS, key="decision")}
    assert {s for s, e in decisions.items() if e.value == "isolated"} == RELAY_5_SITES
    for site in sorted(RELAY_5_SITES):
        route = board.entries(Level.ACCESS, subject=site, key="route")[0]
        assert route.value == "unreachable", site
        assert route.data["medium"] is None, site
    # a misconfigured node is never merely "held", the way a congested one can be
    assert "hold" not in {e.value for e in decisions.values()}


def test_every_plan_is_valid_and_the_most_damaging_cause_goes_first(runs):
    for name, run in runs.items():
        for plan in run.board.entries(Level.PLAN):
            assert plan.data["valid"], f"{name}: {plan.subject} {plan.data['invalid_reason']}"
    plans = sorted(runs["dual-outage"].board.entries(Level.PLAN), key=lambda e: e.data["priority"])
    assert [p.subject for p in plans] == ["SAF_02", "RELAY_5"]
    assert set(plans[0].data["isolated_sites"]) == RELAY_5_SITES


def test_a_cause_affecting_sites_outranks_a_more_certain_local_one(runs):
    """
    RM_07's interference is the more certain hypothesis, but RELAY_5's congestion
    moves four sites off their medium. Damage ranks before certainty.
    """
    plans = sorted(runs["independent-faults"].board.entries(Level.PLAN),
                   key=lambda e: e.data["priority"])
    assert [p.subject for p in plans] == ["RELAY_5", "RM_07"]
    assert set(plans[0].data["affected_sites"]) == RELAY_5_SITES
    assert plans[1].cf > plans[0].cf


# -- (3) control and provenance ----------------------------------------------
@pytest.mark.parametrize("name", sorted(SCENARIOS))
def test_the_controller_reaches_quiescence(name, runs):
    run = runs[name]
    assert run.quiescent, f"{name} stopped at the limit after {run.cycles} cycles"


def test_a_quiescent_board_is_a_fixpoint(topology):
    board = Blackboard()
    TaskGenerator(board).post(build_scenario("dual-outage", topology).observations)
    experts = build_experts(topology)
    Controller(board, experts).loop()
    assert Controller(board, experts).agenda() == []


def test_republishing_the_same_entries_changes_nothing():
    board = Blackboard()
    entry = lambda: Entry(Level.HYPOTHESIS, "X", "diagnosis", "healthy", 0.9, "a", ("S22",))
    assert board.publish("a", [entry()], levels=(Level.HYPOTHESIS,)) == (1, 0)
    version = board.version(Level.HYPOTHESIS)
    assert board.publish("a", [entry()], levels=(Level.HYPOTHESIS,)) == (0, 0)
    assert board.version(Level.HYPOTHESIS) == version


def test_an_expert_cannot_sign_for_another():
    board = Blackboard()
    with pytest.raises(ValueError):
        board.publish("a", [Entry(Level.HYPOTHESIS, "X", "k", "v", 1.0, "b")],
                      levels=(Level.HYPOTHESIS,))


def test_every_entry_has_a_known_author_and_support(runs, topology):
    authors = {e.name for e in build_experts(topology)} | {TASK_GENERATOR}
    rule_ids = {spec[0]: set(spec[5]) for spec in EXPERT_SPECS}
    for name, run in runs.items():
        for entry in run.board.entries():
            assert entry.author in authors, f"{name}: unknown author {entry.author}"
            assert entry.support, f"{name}: {entry.render()} has no support"
            if entry.author in rule_ids:
                assert set(entry.support) <= rule_ids[entry.author], (
                    f"{name}: {entry.render()} cites rules outside its expert"
                )
