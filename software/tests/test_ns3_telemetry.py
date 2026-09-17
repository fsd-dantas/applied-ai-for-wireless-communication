"""
Tests for reading simulated telemetry back as observation records.

PT-BR: Duas propriedades importam. (1) DISCRIMINACAO: so a alcancabilidade ja
       separa um repetidor parado dos nos presos atras dele - o parado esta em
       silencio com o seu proprio salto a montante ainda reportando; o preso
       esta em silencio e o salto a montante tambem. (2) HONESTIDADE: o que o
       simulador nao mede fica DESCONHECIDO com o motivo registrado, e a falha
       comandada nunca e lida.

EN:    Two properties matter. (1) DISCRIMINATION: reachability alone separates a
       stopped relay from the nodes stranded behind it - the stopped one is
       silent while its own upstream still reports; the stranded one is silent
       and so is its upstream. (2) HONESTY: what the simulator cannot measure
       stays UNKNOWN with the reason recorded, and the commanded fault is never
       read.

The expected upstream relations are derived from the declared topology inside
the tests, not hard-coded, so a change to the topology cannot leave a test
asserting a chain that no longer exists.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from aisg.blackboard import build_scenario, unreachable_without
from aisg.domain import load_topology
from aisg.expert_system import (
    FIRING_THRESHOLD,
    InferenceEngine,
    build_simulated_knowledge_base,
)
from aisg.search import shortest_route
from aisg.simulation.telemetry import (
    UNMEASURED,
    TelemetryError,
    diagnose_run,
    observations_from_run,
    read_node_reports,
    score_against_commanded,
    upstream_of,
)

#: The committed run this adapter was built against: SAF_02 stopped, no
#: failover, so nothing masks the outage.
COMMITTED_RUN = (
    Path(__file__).resolve().parents[2]
    / "experiments" / "004-multi-rat-simulation" / "results"
    / "saf-chain-outage" / "none"
)

HEADER = (
    "node,role,window_start_s,window_end_s,heartbeats_expected,"
    "heartbeats_received,loss_pct,last_seen_s,owd_mean_ms"
)
EXPECTED = 13


@pytest.fixture(scope="module")
def topology():
    return load_topology("dual")


@pytest.fixture(scope="module")
def noc(topology):
    return next(n.id for n in topology.nodes.values() if n.kind == "control_centre")


def write_nodes_csv(directory, silent, *, start=16.0, stop=29.0):
    """
    A run in which ``silent`` reported nothing and every other relay reported in
    full. Roles come from the topology, so the fixture cannot drift from it.
    """
    topology = load_topology("dual")
    roles = {
        "saf_relay": "saf", "remote_radio": "rm", "cpe": "cpe", "edge_router": "er",
    }
    lines = [HEADER]
    for node in sorted(topology.nodes.values(), key=lambda n: n.id):
        role = roles.get(node.kind)
        if role is None:
            continue  # the NOC observes; eNodeBs carry no IP stack
        received = 0 if node.id in silent else EXPECTED
        loss = 100.0 * (EXPECTED - received) / EXPECTED
        last_seen = "" if received == 0 else f"{stop:g}"
        owd = 0.0 if received == 0 else 12.5
        lines.append(
            f"{node.id},{role},{start:g},{stop:g},{EXPECTED},{received},"
            f"{loss:.2f},{last_seen},{owd}"
        )
    (directory / "nodes.csv").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return directory


def stranded_behind(topology, relay, noc):
    """A node whose route to the control centre passes through ``relay``."""
    return next(
        node for node in sorted(topology.nodes)
        if upstream_of(topology, node, noc) == relay
    )


# -- (1) discrimination ------------------------------------------------------
def test_a_stopped_relay_and_a_node_behind_it_differ_only_in_the_upstream(
    tmp_path, topology, noc
):
    """
    The whole point of the instrumentation. Both nodes are silent, so packet
    loss and node_responding are identical; the upstream is the only column
    that tells them apart, and it decides which rule fires.
    """
    stopped = "SAF_02"
    assert upstream_of(topology, stopped, noc) is not None
    stranded = stranded_behind(topology, stopped, noc)

    write_nodes_csv(tmp_path, silent={stopped, stranded})
    records = {r.subject_id: r for r in observations_from_run(tmp_path, topology)}

    assert records[stopped].values["node_responding"] == ("no", 1.0)
    assert records[stranded].values["node_responding"] == ("no", 1.0)
    assert records[stopped].values["upstream_relay_reachable"] == ("yes", 1.0)
    assert records[stranded].values["upstream_relay_reachable"] == ("no", 1.0)


def test_reachability_alone_reaches_the_two_diagnoses(tmp_path, topology, noc):
    """
    No PHY or MAC evidence exists in this run, yet S16 and S17 still separate
    the cause from its consequence - the stopped relay outranks nothing, and the
    stranded node's upstream failure outranks its own apparent node failure.
    """
    stopped = "SAF_02"
    stranded = stranded_behind(topology, stopped, noc)
    write_nodes_csv(tmp_path, silent={stopped, stranded})
    records = {r.subject_id: r for r in observations_from_run(tmp_path, topology)}

    def diagnose(subject):
        engine = InferenceEngine(build_simulated_knowledge_base())
        records[subject].apply_to(engine)
        ranked = engine.forward_chain().memory.ranked(
            "diagnosis", min_cf=FIRING_THRESHOLD
        )
        return [(f.value, round(f.cf, 6)) for f in ranked]

    stopped_ranked = diagnose(stopped)
    stranded_ranked = diagnose(stranded)

    assert stopped_ranked[0][0] == "node_failure"
    assert stranded_ranked[0][0] == "upstream_relay_failure"
    # the stranded node also looks unreachable in its own right; what matters is
    # that the cause outranks the symptom
    assert dict(stranded_ranked)["upstream_relay_failure"] > dict(
        stranded_ranked
    ).get("node_failure", 0.0)


def test_a_fully_reporting_network_blames_no_one(tmp_path, topology):
    write_nodes_csv(tmp_path, silent=set())
    for record in observations_from_run(tmp_path, topology):
        assert record.values["node_responding"] == ("yes", 1.0)
        assert record.values["packet_loss_pct"][0] == pytest.approx(0.0)
        assert record.values["neighbours_affected"] == ("none", 1.0)


def test_neighbours_affected_counts_only_silent_declared_neighbours(
    tmp_path, topology, noc
):
    stopped = "SAF_02"
    stranded = stranded_behind(topology, stopped, noc)
    write_nodes_csv(tmp_path, silent={stopped, stranded})
    records = {r.subject_id: r for r in observations_from_run(tmp_path, topology)}

    reporting = [
        r for name, r in records.items()
        if name not in (stopped, stranded)
        and r.values["neighbours_affected"][0] != "none"
    ]
    assert reporting, "a neighbour of the silent pair should notice"
    for record in reporting:
        assert record.values["neighbours_affected"][0] in ("one", "many")


# -- (2) honesty -------------------------------------------------------------
def test_what_the_simulator_cannot_measure_stays_unknown_with_a_reason(
    tmp_path, topology
):
    """
    The property the Prometheus reader established and this adapter inherits: a
    variable with no measurement behind it is absent from `values` and present
    in `unavailable`, with the reason. Never a plausible number.
    """
    write_nodes_csv(tmp_path, silent={"SAF_02"})
    record = observations_from_run(tmp_path, topology)[0]
    for variable, reason in UNMEASURED.items():
        assert variable not in record.values, variable
        assert record.unavailable[variable] == reason
    assert "rssi_dbm" in record.unavailable and "retry_rate_pct" in record.unavailable


def test_records_agree_with_the_knowledge_base(tmp_path, topology):
    kb = build_simulated_knowledge_base()
    write_nodes_csv(tmp_path, silent={"SAF_02"})
    for record in observations_from_run(tmp_path, topology):
        assert record.validate_against(kb) == [], record.subject_id


def test_every_value_carries_its_provenance_and_the_window(tmp_path, topology):
    write_nodes_csv(tmp_path, silent={"SAF_02"})
    for record in observations_from_run(tmp_path, topology):
        assert record.window == "16-29s"
        assert record.captured_at
        assert record.source.startswith("ns3:")
        for variable in record.values:
            assert record.provenance[variable], variable
        # A measured column names the file it was counted in. A derived one
        # names what it was derived from, which for a node reporting straight to
        # the control centre is the observer itself, not the file.
        assert "nodes.csv" in record.provenance["node_responding"]
        assert "nodes.csv" in record.provenance["packet_loss_pct"]


def test_the_commanded_fault_is_never_read(tmp_path, topology):
    """
    `events.csv` is where the commanded fault is recorded. Poisoning it proves
    the adapter never opens it - an unparseable file changes nothing - and the
    records carry only variables that reachability can support.
    """
    write_nodes_csv(tmp_path, silent={"SAF_02"})
    (tmp_path / "events.csv").write_text(
        "10,SAF_02,fault,node_down\x00 and this is not a csv at all\n",
        encoding="utf-8",
    )
    records = observations_from_run(tmp_path, topology)
    assert records
    measurable = {
        "node_responding", "packet_loss_pct",
        "upstream_relay_reachable", "neighbours_affected",
    }
    for record in records:
        assert set(record.values) <= measurable, record.subject_id


def test_a_run_without_the_probe_is_refused_rather_than_diagnosed_empty(
    tmp_path, topology
):
    """A missing file must not read as a healthy network."""
    with pytest.raises(TelemetryError, match="--probe"):
        observations_from_run(tmp_path, topology)


def test_a_malformed_row_names_the_line(tmp_path):
    (tmp_path / "nodes.csv").write_text(
        HEADER + "\nSAF_01,saf,16,29,13,notanumber,0,29,1.0\n", encoding="utf-8"
    )
    with pytest.raises(TelemetryError, match="line 2"):
        read_node_reports(tmp_path)


def test_nodes_the_topology_does_not_declare_are_refused(tmp_path, topology):
    (tmp_path / "nodes.csv").write_text(
        HEADER + "\nGHOST_01,saf,16,29,13,13,0.00,29,1.0\n", encoding="utf-8"
    )
    with pytest.raises(TelemetryError, match="GHOST_01"):
        observations_from_run(tmp_path, topology)


# -- against the real run, not a fixture -------------------------------------
def test_the_measured_silence_matches_the_topology_oracle(topology, noc):
    """
    The nodes the NOC stopped hearing from must be exactly: the stopped relay,
    everything the declared graph says it cuts off, and the one site whose
    primary medium ran through it.

    `unreachable_without` is the blackboard's reachability oracle - breadth-first
    over the declared graph, sharing no code with the simulator - so agreement
    here is two independent routes to the same answer.
    """
    reports = {r.node: r for r in read_node_reports(COMMITTED_RUN)}
    silent = {name for name, report in reports.items() if not report.responding}

    stranded_sites = {
        name for name in reports
        if topology.node(name).kind == "edge_router"
        and "SAF_02" in (shortest_route(topology, noc, name) or [])
    }
    assert stranded_sites == {"ER_06"}
    assert silent == {"SAF_02"} | unreachable_without(topology, ["SAF_02"]) | stranded_sites


def test_the_commanded_outage_is_diagnosed_from_telemetry_alone(topology):
    """
    The completion criterion: the blackboard, fed only what the NOC measured,
    names the node that was actually stopped - and the commanded fault is read
    here, in the evaluator, and nowhere upstream of it.
    """
    run = diagnose_run(COMMITTED_RUN, topology)
    commanded = build_scenario("saf-chain-outage", topology).commanded
    assert commanded == {"SAF_02": "node_failure"}

    score = score_against_commanded(run, commanded)
    assert score.missed == ()
    assert score.hits == (("SAF_02", "node_failure"),)
    assert run.quiescent


# -- the evaluator, which is the only thing allowed to see the answer --------
def test_scoring_separates_the_commanded_cause_from_its_consequences():
    class _Entry:
        def __init__(self, subject, value):
            self.subject, self.value = subject, value

    class _Board:
        def entries(self, *_args, **_kwargs):
            return [
                _Entry("SAF_02", "node_failure"),
                _Entry("SAF_03", "upstream_relay_failure"),
            ]

    class _Run:
        board = _Board()

    score = score_against_commanded(_Run(), {"SAF_02": "node_failure"})
    assert score.hits == (("SAF_02", "node_failure"),)
    assert score.missed == ()
    assert score.exact
    # a correctly diagnosed consequence is reported, not counted as an error
    assert score.spurious == (("SAF_03", "upstream_relay_failure"),)
