"""
Read simulated telemetry back as observation records.

PT-BR: Fecha o ciclo diagnostico -> plano -> verificacao pelo lado que faltava.
       O simulador mede; este modulo traduz a medida para o vocabulario da base
       de conhecimento; o quadro-negro diagnostica. A falha COMANDADA nao entra
       aqui em nenhum momento: ela existe no cenario apenas para pontuar o
       resultado depois, e `events.csv` - onde a falha comandada esta registrada
       - nunca e lido.

       O que nao pode ser medido fica DESCONHECIDO, com o motivo escrito no
       registro. E o mesmo contrato do leitor de Prometheus: instrumentar mais
       aumenta a cobertura, e nada e inventado enquanto isso.

EN:    Implements offline diagnosis from recorded simulator measurements.
       It does not apply the resulting actions back to the simulator.
       The simulator measures; this module translates the measurement
       into the knowledge base's vocabulary; the blackboard diagnoses. The
       COMMANDED fault never enters here: it exists in the scenario only to score
       the result afterwards, and `events.csv` - which is where the commanded
       fault is recorded - is never read.

       What cannot be measured stays UNKNOWN, with the reason written into the
       record. Same contract as the Prometheus reader: instrumenting more raises
       coverage, and nothing is invented in the meantime.

Evidencia disponivel / Available evidence
-----------------------------------------
``nodes.csv``, written by the simulator's ``--probe`` flag: per node, how many
heartbeats the NOC expected in the measurement window and how many arrived.
Reachability is the whole of it - and it is enough, because the two diagnoses a
relay chain produces turn on exactly two booleans:

    S16  node_responding = no                                  -> node_failure
    S17  node_responding = no AND upstream_relay_reachable = no -> upstream_relay_failure

A stopped relay is silent while its own upstream still reports. A node stranded
behind it is silent AND its upstream is silent. That is the discriminator, and
no PHY or MAC quantity is needed for it.
"""

from __future__ import annotations

import csv
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Mapping, Optional, Tuple

from aisg.domain.topology import Topology
from aisg.observation import Observation, _now
from aisg.search import shortest_route

#: Written by `dual-homed-backhaul --probe`.
NODES_CSV = "nodes.csv"

#: Certainty of a reachability reading. A heartbeat either arrived or it did
#: not, and the simulator is the ground on which it is counted, so 1.0 - unlike
#: an operator reading a spectrum sweep by eye.
REACHABILITY_CF = 1.0

#: How many silent neighbours count as `many`. Two is the smallest number that
#: is not `one`, and the label domain has nothing between them.
MANY_NEIGHBOURS = 2

#: Why each askable variable has NO measurement behind it in this simulator.
#: These become `unavailable` entries: the variable stays unknown and the record
#: says why, rather than going quietly missing.
UNMEASURED: Dict[str, str] = {
    "rssi_dbm":
        "the 900 MHz radio is an abstract point-to-point link; no receiver reports power",
    "snr_db":
        "same abstraction: no signal-to-noise ratio is computed per received frame",
    "excess_path_loss_db":
        "propagation loss is a declared scenario parameter, not a measured quantity",
    "retry_rate_pct":
        "the point-to-point model has no contention MAC, so no retry is ever counted",
    "rtt_ms":
        "node heartbeats are one-way; the scenario installs no forward route to a "
        "relay, so the NOC cannot reply and no round trip exists to time",
    "offered_load_pct":
        "no per-node capacity is declared, so offered load has no denominator",
    "co_channel_emitter":
        "no emitter inventory is simulated",
    "nodes_sharing_channel":
        "every radio hop is a dedicated link; no channel is shared",
    "route_present":
        "no routing table is exported; silence does not prove a route is missing",
}


class TelemetryError(ValueError):
    """Raised when a results directory cannot be read as telemetry."""


@dataclass(frozen=True)
class NodeReport:
    """One node's reachability over one measurement window."""

    node: str
    role: str
    window_start_s: float
    window_end_s: float
    expected: int
    received: int
    loss_pct: float
    last_seen_s: Optional[float]
    owd_mean_ms: float

    def __post_init__(self) -> None:
        numbers = (self.window_start_s, self.window_end_s, self.loss_pct, self.owd_mean_ms)
        if not all(math.isfinite(value) for value in numbers):
            raise ValueError("telemetry values must be finite")
        if self.window_start_s < 0 or self.window_end_s <= self.window_start_s:
            raise ValueError("invalid measurement window")
        if self.expected <= 0 or not 0 <= self.received <= self.expected:
            raise ValueError("heartbeat counts require expected > 0 and 0 <= received <= expected")
        expected_loss = 100.0 * (self.expected - self.received) / self.expected
        if not 0 <= self.loss_pct <= 100 or abs(self.loss_pct - expected_loss) > 0.011:
            raise ValueError("loss_pct disagrees with heartbeat counts")
        if self.owd_mean_ms < 0:
            raise ValueError("one-way delay cannot be negative")
        if (self.last_seen_s is not None) != (self.received > 0):
            raise ValueError("last_seen_s must be present exactly when heartbeats arrived")
        # The window identifies send times; packets may arrive after its end.
        if self.last_seen_s is not None and (
            not math.isfinite(self.last_seen_s) or self.last_seen_s < self.window_start_s
        ):
            raise ValueError("invalid last_seen_s")

    @property
    def responding(self) -> bool:
        """Whether anything at all arrived from this node in the window."""
        return self.received > 0

    @property
    def window(self) -> str:
        return f"{self.window_start_s:g}-{self.window_end_s:g}s"


def read_node_reports(results_dir: Path | str) -> List[NodeReport]:
    """
    Read ``nodes.csv`` from a simulator run.

    Raises rather than returning nothing: a caller that silently got an empty
    list would diagnose an empty network and call it healthy.
    """
    path = Path(results_dir) / NODES_CSV
    if not path.is_file():
        raise TelemetryError(
            f"{path} not found; the run must be made with --probe for the NOC to "
            f"record per-node reachability"
        )
    reports: List[NodeReport] = []
    with path.open(encoding="utf-8", newline="") as handle:
        for number, row in enumerate(csv.DictReader(handle), start=2):
            try:
                last_seen = row["last_seen_s"].strip()
                reports.append(NodeReport(
                    node=row["node"],
                    role=row["role"],
                    window_start_s=float(row["window_start_s"]),
                    window_end_s=float(row["window_end_s"]),
                    expected=int(row["heartbeats_expected"]),
                    received=int(row["heartbeats_received"]),
                    loss_pct=float(row["loss_pct"]),
                    last_seen_s=float(last_seen) if last_seen else None,
                    owd_mean_ms=float(row["owd_mean_ms"]),
                ))
            except (KeyError, ValueError, TypeError, AttributeError) as exc:
                raise TelemetryError(f"{path}: line {number}: {exc}") from None
    if not reports:
        raise TelemetryError(f"{path} declares no node")
    if len({r.node for r in reports}) != len(reports):
        raise TelemetryError(f"{path}: duplicate node reports")
    if len({(r.window_start_s, r.window_end_s) for r in reports}) != 1:
        raise TelemetryError(f"{path}: node reports must share one measurement window")
    return reports


def control_centre(topology: Topology) -> str:
    for node in topology.nodes.values():
        if node.kind == "control_centre":
            return node.id
    raise TelemetryError("the topology declares no control centre to observe from")


def upstream_of(topology: Topology, node: str, source: str) -> Optional[str]:
    """
    The hop a node's traffic reaches the control centre through.

    Declared topology, not commanded truth: this is the network model any
    management system already has. ``None`` when the node IS the source or has
    no route to it.
    """
    if node == source:
        return None
    route = shortest_route(topology, source, node)
    if route is None or len(route) < 2:
        return None
    return route[-2]


def _neighbours_affected(
    topology: Topology, node: str, reports: Mapping[str, NodeReport]
) -> Tuple[str, int]:
    """How many of a node's neighbours went silent too, as a declared label."""
    silent = 0
    for neighbour, _link in topology.neighbours(node):
        report = reports.get(neighbour)
        if report is not None and not report.responding:
            silent += 1
    if silent == 0:
        return "none", 0
    if silent == 1:
        return "one", 1
    return "many", silent


def observation_for(
    report: NodeReport,
    topology: Topology,
    reports: Mapping[str, NodeReport],
    source_node: str,
    *,
    source: str,
    captured_at: str = "",
) -> Observation:
    """
    Translate one node's reachability into the knowledge base's vocabulary.

    Every value carries its provenance; every variable with no measurement
    behind it carries the reason it has none.
    """
    record = Observation(
        subject_id=report.node,
        subject_kind="node",
        captured_at=captured_at or _now(),
        source=source,
        window=report.window,
    )
    where = f"{NODES_CSV}:{report.node} over {report.window} of simulated time"

    record.values["node_responding"] = (
        "yes" if report.responding else "no", REACHABILITY_CF
    )
    record.provenance["node_responding"] = (
        f"{where}: heartbeats_received = {report.received} of "
        f"{report.expected} expected"
    )

    record.values["packet_loss_pct"] = (report.loss_pct, REACHABILITY_CF)
    record.provenance["packet_loss_pct"] = (
        f"{where}: loss_pct over the node's own heartbeats, not over site traffic"
    )

    upstream = upstream_of(topology, report.node, source_node)
    if upstream is None:
        record.unavailable["upstream_relay_reachable"] = (
            "No upstream route is known in the declared topology"
        )
    elif upstream == source_node:
        # The control centre is the observer. Everything in this file arrived
        # there, so treating it as reachable states a fact, not an assumption.
        record.values["upstream_relay_reachable"] = ("yes", REACHABILITY_CF)
        record.provenance["upstream_relay_reachable"] = (
            f"{report.node} reports directly to {source_node}, which is the "
            f"observer and received this file"
        )
    elif upstream in reports:
        reachable = reports[upstream].responding
        record.values["upstream_relay_reachable"] = (
            "yes" if reachable else "no", REACHABILITY_CF
        )
        record.provenance["upstream_relay_reachable"] = (
            f"{NODES_CSV}:{upstream}, the hop {report.node} reaches "
            f"{source_node} through: heartbeats_received = "
            f"{reports[upstream].received}"
        )
    else:
        record.unavailable["upstream_relay_reachable"] = (
            f"{upstream}, the upstream hop, reports no heartbeat of its own "
            f"(an eNodeB carries no IP stack in this model)"
        )

    missing = {
        neighbour for neighbour, _ in topology.neighbours(report.node)
        if neighbour != source_node and neighbour not in reports
    }
    label, silent = _neighbours_affected(topology, report.node, reports)
    if missing and silent < MANY_NEIGHBOURS:
        record.unavailable["neighbours_affected"] = (
            f"Missing neighbour telemetry: {', '.join(sorted(missing))}"
        )
    else:
        record.values["neighbours_affected"] = (label, REACHABILITY_CF)
        record.provenance["neighbours_affected"] = (
            f"{NODES_CSV}: {silent} declared neighbours of {report.node} "
            f"reported nothing in the same window"
        )

    for variable, reason in UNMEASURED.items():
        if variable not in record.values:
            record.unavailable[variable] = reason
    return record


def observations_from_run(
    results_dir: Path | str,
    topology: Topology,
    *,
    source: str = "",
    captured_at: str = "",
) -> List[Observation]:
    """
    Every node's observation record for one simulator run.

    Reads ``nodes.csv`` only. ``events.csv`` holds the commanded fault and is
    deliberately never opened by this module.
    """
    reports = {r.node: r for r in read_node_reports(results_dir)}
    unknown = sorted(set(reports) - set(topology.nodes))
    if unknown:
        raise TelemetryError(
            f"{NODES_CSV} reports nodes the topology does not declare: "
            f"{', '.join(unknown)}"
        )
    source_node = control_centre(topology)
    origin = source or f"ns3:{Path(results_dir).as_posix()}"
    return [
        observation_for(
            reports[name], topology, reports, source_node,
            source=origin, captured_at=captured_at,
        )
        for name in sorted(reports)
    ]


def diagnose_run(
    results_dir: Path | str,
    topology: Topology,
    *,
    limit: int = 100,
    source: str = "",
):
    """
    Post a run's telemetry on the blackboard and reason to quiescence.

    The same board, controller and experts the hand-written scenarios use: the
    only thing that changes is where the evidence came from.
    """
    # Imported here, as the exporter does: the blackboard is not needed to read
    # telemetry, and importing it at module scope would tie the two together.
    from aisg.blackboard import Blackboard, Controller, TaskGenerator, build_experts

    observations = observations_from_run(
        results_dir, topology, source=source
    )
    board = Blackboard()
    TaskGenerator(board).post(observations)
    return Controller(board, build_experts(topology), limit=limit).loop()


# ---------------------------------------------------------------------------
# evaluation: the ONLY place commanded truth is allowed
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Score:
    """How a telemetry-driven diagnosis compares with what was commanded."""

    found: Tuple[Tuple[str, str], ...]
    commanded: Tuple[Tuple[str, str], ...]

    @property
    def hits(self) -> Tuple[Tuple[str, str], ...]:
        return tuple(sorted(set(self.found) & set(self.commanded)))

    @property
    def missed(self) -> Tuple[Tuple[str, str], ...]:
        return tuple(sorted(set(self.commanded) - set(self.found)))

    @property
    def spurious(self) -> Tuple[Tuple[str, str], ...]:
        """Incidents on nodes where nothing was commanded.

        This is an unmatched-node report, not proof of false positives: downstream
        consequences require separate expected labels. Exact incident-set matching
        is intentionally stricter and permits no extra diagnosis pairs.
        """
        commanded_nodes = {node for node, _ in self.commanded}
        return tuple(sorted(f for f in self.found if f[0] not in commanded_nodes))

    @property
    def exact(self) -> bool:
        """Exact incident-set agreement, including absence of extra diagnoses."""
        return set(self.found) == set(self.commanded)


def score_against_commanded(run, commanded: Mapping[str, str]) -> Score:
    """
    Compare a diagnosis with the commanded fault.

    SCORING ONLY. Nothing upstream of this function reads `commanded`: the
    adapter never opens `events.csv`, and no expert is given the scenario. The
    separation is the point of the exercise - a diagnosis that has seen the
    answer demonstrates nothing.
    """
    from aisg.blackboard import Level

    found = tuple(sorted(
        (entry.subject, str(entry.value))
        for entry in run.board.entries(Level.INCIDENT, key="incident")
    ))
    return Score(found=found, commanded=tuple(sorted(commanded.items())))
