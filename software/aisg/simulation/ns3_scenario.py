"""
Export the dual-homed backhaul as an ns-3 scenario file.

PT-BR: Converte a topologia declarada no arquivo lido pelo programa ns-3
       ``dual-homed-backhaul``. A topologia continua sendo a unica fonte de
       verdade: nos, enlaces, enderecos, rotas estaticas e parametros de radio
       saem daqui, de forma deterministica.

       Tres decisoes de modelagem, declaradas:

       * os repetidores LTE viram eNodeBs, porque o modulo LTE do ns-3 nao
         implementa repetidores; o enlace entre eles e substituido pela
         interface S1 que o EPC cria;
       * cada salto de 900 MHz armazena-e-encaminha e um enlace ponto a ponto
         com taxa nominal, atraso de propagacao somado a sobrecarga do modelo
         de custo, e taxa de erro de pacote derivada de um orcamento de enlace;
       * as rotas estaticas pela malha de 900 MHz sao calculadas pelo mesmo A*
         do roteamento.

EN:    Converts the declared topology into the file read by the ns-3 program
       ``dual-homed-backhaul``. The topology stays the single source of truth:
       nodes, links, addresses, static routes and radio parameters come from
       here, deterministically.

       Three declared modelling decisions:

       * LTE relays become eNodeBs, because the ns-3 LTE module implements no
         relays; the link between them is replaced by the S1 interface the EPC
         creates;
       * every 900 MHz store-and-forward hop is a point-to-point link with a
         nominal rate, propagation delay plus the cost model's overhead, and a
         packet error rate derived from a link budget;
       * static routes across the 900 MHz mesh are computed by the same A* used
         for routing.

Scenario format / Formato do cenario
------------------------------------
Line oriented, whitespace separated, ``#`` starts a comment::

    aisg-ns3-scenario 1
    param <name> <value>
    node  <id> <role> <x_m> <y_m>                      role: noc enb cpe saf rm er
    p2p   <id> <a> <b> <class> <rate> <delay_ms> <per> <network/24> <rssi_dbm|-> <snr_db|->
    attach <cpe> <enb>
    site  <er> <rm> <cpe> <primary: radio900|plte> <index>
    route <node> <destination: noc|ER id> <next hop: node id|tunnel>
    path  <er> <medium: radio900|plte> <NOC next hop|tunnel> <ER next hop>
    fault <time_s> <kind: node_down|radio_per|flood> <target: node|link id|eNodeB> <value|->
    failover <time_s> <er> <medium>                    central plan from the blackboard

Faults and the central failover plan are written only when a fault scenario is
requested. Their ground truth is the blackboard scenario's commanded faults.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Mapping, Optional, Tuple

from aisg.domain.diagnoses import DIAGNOSES, FaultMechanism
from aisg.domain.topology import LINK_TYPES, Topology
from aisg.search import shortest_route

FORMAT_HEADER = "aisg-ns3-scenario 1"

SPEED_OF_LIGHT_M_S = 299_792_458.0
FIBRE_SPEED_M_S = 2.0e8

#: NOMINAL, UNCALIBRATED. Every simulation parameter lives in this one block.
NS3_PARAMETERS: Dict[str, object] = {
    "sim_time_s": 30.0,
    "traffic_start_s": 2.0,
    # wired
    "fibre_rate": "1Gbps",
    "wired_rate": "100Mbps",
    # 900 MHz store-and-forward radio
    "radio_rate": "256kbps",
    "radio_queue_packets": 100,
    "radio_frequency_hz": 900.0e6,
    "radio_bandwidth_hz": 250.0e3,
    "radio_tx_power_dbm": 30.0,
    "radio_antenna_gain_dbi": 10.0,
    "radio_noise_figure_db": 5.0,
    "radio_pathloss_exponent_saf": 2.7,
    "radio_pathloss_exponent_access": 3.0,
    "reference_packet_bytes": 512,
    # private LTE, band 31 (DL 462.5-467.5 MHz, UL 452.5-457.5 MHz), 5 MHz carrier
    "lte_earfcn_dl": 9895,
    "lte_earfcn_ul": 27235,
    "lte_dl_frequency_hz": 465.0e6,
    "lte_bandwidth_rb": 25,
    "enb_tx_power_dbm": 46.0,
    "ue_tx_power_dbm": 23.0,
    # Fixed outdoor CPE: a directional antenna aimed at its serving eNodeB. With
    # an isotropic 23 dBm CPE the uplink of the farthest sites does not close.
    "cpe_antenna_max_gain_dbi": 12.0,
    "cpe_antenna_beamwidth_deg": 65.0,
    # traffic
    "scada_interval_s": 2.0,
    "scada_request_bytes": 64,
    "scada_response_bytes": 256,
    "telemetry_interval_s": 1.0,
    "telemetry_bytes": 512,
    "tunnel_port": 6600,
    # faults and failover
    "fault_time_s": 10.0,
    "central_decision_delay_s": 3.0,
    "local_miss_threshold": 3,
    "interference_per": 0.6,
    "flood_rate": "20Mbps",
}

#: How each commanded diagnosis is induced in the simulator.
FAULT_BY_DIAGNOSIS: Dict[str, str] = {
    name: contract.simulation.mechanism.value
    for name, contract in DIAGNOSES.items()
    if contract.simulation.mechanism is not None
}

#: Topology node kinds and the role each plays in the simulation.
ROLE_BY_KIND: Dict[str, str] = {
    "control_centre": "noc",
    "lte_enb": "enb",
    "lte_relay": "enb",
    "cpe": "cpe",
    "saf_relay": "saf",
    "remote_radio": "rm",
    "edge_router": "er",
}

_NETWORK_OCTET = {"fibre": 1, "radio": 2, "wired": 3}


class ScenarioError(ValueError):
    """Raised when the topology cannot be expressed as a dual-homed ns-3 scenario."""


@dataclass(frozen=True)
class LinkBudget:
    rssi_dbm: float
    snr_db: float
    packet_error_rate: float


@dataclass(frozen=True)
class P2PLink:
    id: str
    a: str
    b: str
    cls: str
    rate: str
    delay_ms: float
    per: float
    network: str
    rssi_dbm: Optional[float] = None
    snr_db: Optional[float] = None


@dataclass(frozen=True)
class Site:
    er: str
    rm: str
    cpe: str
    primary: str
    index: int


@dataclass
class Ns3Scenario:
    topology_id: str
    params: Dict[str, object]
    nodes: List[Tuple[str, str, float, float]] = field(default_factory=list)
    links: List[P2PLink] = field(default_factory=list)
    attachments: List[Tuple[str, str]] = field(default_factory=list)
    sites: List[Site] = field(default_factory=list)
    routes: Dict[Tuple[str, str], str] = field(default_factory=dict)
    #: (er, medium, NOC next hop, ER next hop) for both media of every site
    paths: List[Tuple[str, str, str, str]] = field(default_factory=list)
    #: (time_s, kind, target, value)
    faults: List[Tuple[float, str, str, str]] = field(default_factory=list)
    #: (time_s, er, medium): the central failover plan
    failovers: List[Tuple[float, str, str]] = field(default_factory=list)
    fault_scenario: Optional[str] = None
    notes: List[str] = field(default_factory=list)

    def render(self) -> str:
        lines = [
            FORMAT_HEADER,
            f"# exported by aisg from topology '{self.topology_id}'",
            "# SYNTHETIC scenario; every parameter is nominal and uncalibrated",
        ]
        lines += [f"# {note}" for note in self.notes]
        lines += [f"param {name} {_fmt(self.params[name])}" for name in sorted(self.params)]
        lines += [f"node {nid} {role} {x:g} {y:g}" for nid, role, x, y in self.nodes]
        for link in self.links:
            rssi = "-" if link.rssi_dbm is None else f"{link.rssi_dbm:.1f}"
            snr = "-" if link.snr_db is None else f"{link.snr_db:.1f}"
            lines.append(
                f"p2p {link.id} {link.a} {link.b} {link.cls} {link.rate} "
                f"{link.delay_ms:.4f} {link.per:.6g} {link.network} {rssi} {snr}"
            )
        lines += [f"attach {cpe} {enb}" for cpe, enb in self.attachments]
        lines += [
            f"site {s.er} {s.rm} {s.cpe} {s.primary} {s.index}" for s in self.sites
        ]
        lines += [f"route {node} {dest} {via}" for (node, dest), via in self.routes.items()]
        lines += [f"path {er} {medium} {noc_via} {er_via}" for er, medium, noc_via, er_via in self.paths]
        if self.fault_scenario:
            lines.append(f"# fault scenario '{self.fault_scenario}'; ground truth for scoring only")
        lines += [f"fault {t:g} {kind} {target} {value}" for t, kind, target, value in self.faults]
        lines += [f"failover {t:g} {er} {medium}" for t, er, medium in self.failovers]
        return "\n".join(lines) + "\n"

    def write(self, path: Path | str) -> None:
        Path(path).write_text(self.render(), encoding="utf-8", newline="\n")


def _fmt(value: object) -> str:
    if isinstance(value, float):
        return f"{value:g}"
    return str(value)


def radio_link_budget(
    distance_m: float,
    quality: float,
    exponent: float,
    params: Mapping[str, object] = NS3_PARAMETERS,
) -> LinkBudget:
    """
    Received power, SNR and packet error rate of one 900 MHz hop.

    PT-BR: Perda log-distancia com referencia no espaco livre a 1 m, degradada
           pela qualidade declarada do enlace; BER de BPSK; PER para o pacote
           de referencia. Tudo nominal: serve para parametrizar o simulador, nao
           para descrever um radio real.
    EN:    Log-distance loss referenced to free space at 1 m, degraded by the
           link's declared quality; BPSK bit error rate; packet error rate for
           the reference packet. All nominal: it parameterises the simulator, it
           does not describe a real radio.
    """
    frequency = float(params["radio_frequency_hz"])
    reference_loss = 20 * math.log10(4 * math.pi * frequency / SPEED_OF_LIGHT_M_S)
    path_loss = (
        reference_loss
        + 10 * exponent * math.log10(max(distance_m, 1.0))
        + 20 * math.log10(1.0 / quality)
    )
    rssi = (
        float(params["radio_tx_power_dbm"])
        + 2 * float(params["radio_antenna_gain_dbi"])
        - path_loss
    )
    noise = (
        -174.0
        + 10 * math.log10(float(params["radio_bandwidth_hz"]))
        + float(params["radio_noise_figure_db"])
    )
    snr_db = rssi - noise
    ber = 0.5 * math.erfc(math.sqrt(10 ** (snr_db / 10)))
    bits = 8 * int(params["reference_packet_bytes"])
    per = -math.expm1(bits * math.log1p(-ber)) if ber < 1.0 else 1.0
    return LinkBudget(rssi, snr_db, per)


def _path_medium(topology: Topology, path: List[str]) -> str:
    types = set()
    for u, v in zip(path, path[1:]):
        link = min(
            (lk for nb, lk in topology.neighbours(u) if nb == v), key=topology.link_cost
        )
        types.add(link.type)
    return "plte" if "lte" in types else "radio900"


def build_ns3_scenario(
    topology: Topology,
    params: Optional[Mapping[str, object]] = None,
    fault_scenario: Optional[str] = None,
) -> Ns3Scenario:
    """
    Build the dual-homed scenario; raises :class:`ScenarioError` when it cannot.

    PT-BR: Com ``fault_scenario``, injeta as falhas comandadas de um cenario do
           quadro-negro e grava o plano de failover central que o proprio
           quadro-negro recomenda, para que o simulador o verifique.
    EN:    With ``fault_scenario``, injects a blackboard scenario's commanded
           faults and writes the central failover plan the blackboard itself
           recommends, so the simulator can check it.
    """
    p: Dict[str, object] = dict(NS3_PARAMETERS)
    p.update(params or {})

    roles: Dict[str, str] = {}
    for node in topology.nodes.values():
        if node.kind not in ROLE_BY_KIND:
            raise ScenarioError(f"node {node.id}: kind {node.kind!r} has no simulation role")
        roles[node.id] = ROLE_BY_KIND[node.kind]
    nocs = [nid for nid, role in roles.items() if role == "noc"]
    if len(nocs) != 1:
        raise ScenarioError(f"expected exactly one control centre, found {len(nocs)}")
    noc = nocs[0]

    scenario = Ns3Scenario(topology_id=topology.id, params=p)
    scenario.nodes = [(n.id, roles[n.id], n.x, n.y) for n in topology.nodes.values()]
    relays = sorted(n.id for n in topology.nodes.values() if n.kind == "lte_relay")
    if relays:
        scenario.notes.append(
            f"LTE relays modelled as eNodeBs (ns-3 has no LTE relay): {', '.join(relays)}"
        )

    counters = {cls: 0 for cls in _NETWORK_OCTET}
    for link in topology.links:
        ra, rb = roles[link.a], roles[link.b]
        if link.type == "lte":
            if {ra, rb} == {"cpe", "enb"}:
                cpe, enb = (link.a, link.b) if ra == "cpe" else (link.b, link.a)
                scenario.attachments.append((cpe, enb))
                continue
            if ra == rb == "enb":
                scenario.notes.append(
                    f"dropped LTE relay backhaul {link.a}-{link.b}: replaced by the EPC S1 interface"
                )
                continue
            raise ScenarioError(f"LTE link {link.a}-{link.b} joins {ra} and {rb}")
        if link.type == "fiber" and "enb" in (ra, rb):
            scenario.notes.append(
                f"dropped fibre {link.a}-{link.b}: eNodeBs reach the core through the EPC S1 interface"
            )
            continue

        distance = topology.distance(link.a, link.b)
        overhead = LINK_TYPES[link.type].overhead_ms
        rssi = snr = None
        if link.type == "fiber":
            cls, rate, per = "fibre", str(p["fibre_rate"]), 0.0
            delay = distance / FIBRE_SPEED_M_S * 1e3
        elif link.type == "ethernet":
            cls, rate, per = "wired", str(p["wired_rate"]), 0.0
            delay = distance / FIBRE_SPEED_M_S * 1e3 + overhead
        elif link.type in ("radio_900mhz", "radio_900mhz_saf"):
            exponent = float(
                p["radio_pathloss_exponent_saf"]
                if link.type == "radio_900mhz_saf"
                else p["radio_pathloss_exponent_access"]
            )
            budget = radio_link_budget(distance, link.quality, exponent, p)
            cls, rate, per = "radio", str(p["radio_rate"]), budget.packet_error_rate
            rssi, snr = budget.rssi_dbm, budget.snr_db
            delay = distance / SPEED_OF_LIGHT_M_S * 1e3 + overhead
        else:
            raise ScenarioError(f"link {link.a}-{link.b}: unsupported type {link.type!r}")

        index = counters[cls]
        if index > 255:
            raise ScenarioError(f"more than 256 {cls} links; the /24 address plan is exhausted")
        counters[cls] += 1
        scenario.links.append(P2PLink(
            id=f"L{len(scenario.links) + 1:03d}",
            a=link.a, b=link.b, cls=cls, rate=rate,
            delay_ms=round(delay, 4), per=per,
            network=f"10.{_NETWORK_OCTET[cls]}.{index}.0",
            rssi_dbm=rssi, snr_db=snr,
        ))

    attached = [cpe for cpe, _ in scenario.attachments]
    cpes = sorted(nid for nid, role in roles.items() if role == "cpe")
    if sorted(attached) != cpes:
        raise ScenarioError("every CPE must attach to exactly one eNodeB")

    wired_neighbours: Dict[str, List[str]] = {}
    for link in scenario.links:
        if link.cls == "wired":
            wired_neighbours.setdefault(link.a, []).append(link.b)
            wired_neighbours.setdefault(link.b, []).append(link.a)

    edge_routers = sorted(nid for nid, role in roles.items() if role == "er")
    if len(edge_routers) > 255:
        raise ScenarioError("more than 255 sites; the site address plan is exhausted")
    for index, er in enumerate(edge_routers, start=1):
        neighbours = wired_neighbours.get(er, [])
        rms = [n for n in neighbours if roles[n] == "rm"]
        site_cpes = [n for n in neighbours if roles[n] == "cpe"]
        if len(rms) != 1 or len(site_cpes) != 1:
            raise ScenarioError(
                f"{er} must be wired to exactly one remote radio and one CPE "
                f"(found {len(rms)} and {len(site_cpes)})"
            )
        nominal = shortest_route(topology, noc, er)
        if nominal is None:
            raise ScenarioError(f"{er} is unreachable from {noc}")
        scenario.sites.append(Site(er, rms[0], site_cpes[0], _path_medium(topology, nominal), index))

    lte_side = tuple(nid for nid, role in roles.items() if role in ("enb", "cpe"))

    def add_route(node: str, dest: str, via: str) -> None:
        key = (node, dest)
        if key in scenario.routes and scenario.routes[key] != via:
            raise ScenarioError(
                f"conflicting routes at {node} towards {dest}: "
                f"{scenario.routes[key]} and {via}"
            )
        scenario.routes[key] = via

    for site in scenario.sites:
        path = shortest_route(topology, noc, site.er, avoid=lte_side)
        if path is None or path[-2] != site.rm:
            raise ScenarioError(f"{site.er} has no 900 MHz route ending at {site.rm}")
        for u, v in zip(path[1:-1], path[2:]):
            add_route(u, site.er, v)
        for u, v in zip(path[1:-1], path[:-2]):
            add_route(u, "noc", v)
        add_route(noc, site.er, path[1] if site.primary == "radio900" else "tunnel")
        add_route(site.er, "noc", site.rm if site.primary == "radio900" else site.cpe)
        add_route(site.cpe, site.er, site.er)
        add_route(site.cpe, "noc", "tunnel")
        scenario.paths.append((site.er, "radio900", path[1], site.rm))
        scenario.paths.append((site.er, "plte", "tunnel", site.cpe))

    if fault_scenario is not None:
        _add_faults(scenario, topology, roles, fault_scenario)
    return scenario


def _add_faults(
    scenario: Ns3Scenario, topology: Topology, roles: Mapping[str, str], name: str
) -> None:
    # Imported here: the blackboard is only needed when faults are requested.
    from aisg.blackboard import SCENARIOS, Level, build_scenario, solve

    if name not in SCENARIOS:
        raise ScenarioError(
            f"unknown fault scenario {name!r}; available: {', '.join(sorted(SCENARIOS))}"
        )
    p = scenario.params
    board_scenario = build_scenario(name, topology)
    fault_time = float(p["fault_time_s"])
    scenario.fault_scenario = name
    p["fault_scenario"] = name

    radio_links: Dict[str, List[P2PLink]] = {}
    for link in scenario.links:
        if link.cls == "radio":
            radio_links.setdefault(link.a, []).append(link)
            radio_links.setdefault(link.b, []).append(link)

    for node, diagnosis in sorted(board_scenario.commanded.items()):
        kind = FAULT_BY_DIAGNOSIS.get(diagnosis)
        if kind is None:
            raise ScenarioError(f"{node}: no way to induce {diagnosis!r} in the simulator")
        if kind == "node_down":
            scenario.faults.append((fault_time, "node_down", node, "-"))
        elif kind == "radio_per":
            links = radio_links.get(node)
            if not links:
                raise ScenarioError(f"{node}: {diagnosis} needs a radio link, and it has none")
            for link in links:
                scenario.faults.append(
                    (fault_time, "radio_per", link.id, _fmt(float(p["interference_per"])))
                )
        elif kind == "flood":
            if roles[node] != "enb":
                raise ScenarioError(f"{node}: congestion is only modelled on an eNodeB")
            scenario.faults.append((fault_time, "flood", node, str(p["flood_rate"])))
        else:
            # A mechanism the contract declares but this exporter does not
            # dispatch. Refusing beats emitting a scenario with no fault in it,
            # which would then be scored against predictions expecting one.
            raise ScenarioError(
                f"{node}: mechanism {kind!r} for {diagnosis!r} is declared in the "
                f"diagnosis contract but not implemented by this exporter; "
                f"implemented: {', '.join(m.value for m in FaultMechanism)}"
            )

    run = solve(board_scenario, topology)
    decided_at = fault_time + float(p["central_decision_delay_s"])
    sites = {site.er for site in scenario.sites}
    for decision in sorted(
        run.board.entries(Level.ACCESS, key="decision"), key=lambda e: e.subject
    ):
        if decision.value == "switch_medium" and decision.subject in sites:
            scenario.failovers.append((decided_at, decision.subject, decision.data["to"]))
