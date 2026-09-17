"""
Eco-resolution on the dual-homed backhaul: traffic flows competing for media.

PT-BR: Cada site tem dois fluxos, cada um e um eco-agente: SCADA (prioridade 2)
       e telemetria (prioridade 1). Os LUGARES sao os dois meios de acesso do
       site. Um meio consome capacidade dos seus gargalos: a celula do eNodeB
       servidor, no LTE privativo, e cada repetidor armazena-e-encaminha do
       caminho, no 900 MHz. Ha ainda o lugar ESTACIONADO: o fluxo deixa de
       transmitir, sempre possivel, e insatisfatorio.

       * satisfeito: num meio sem no parado nem degradado, e dentro da capacidade
         de todos os gargalos pela ordem de prioridade;
       * impedido: um gargalo esta cheio; so um fluxo de prioridade ESTRITAMENTE
         menor pode ser agredido, o que exclui o pingue-pongue entre iguais;
       * fuga: para o outro meio, se couber, ou estacionar;
       * dependencia: a telemetria de um site so age depois que o SCADA desse site
         esta satisfeito.

       O estado do mundo vem dos INCIDENTES que o quadro-negro diagnosticou, e nao
       da falha comandada: parada vira no parado, interferencia vira no degradado,
       congestionamento vira capacidade reduzida. As capacidades sao nominais.

       Diferenca de desenho em relacao ao quadro-negro: o arbitro decide por site;
       aqui cada fluxo decide por si, e os dois fluxos de um site podem terminar em
       meios diferentes. A decisao vale para as duas extremidades do fluxo ao mesmo
       tempo - e isso que evita a oscilacao do failover local no experimento 004.

EN:    Every site has two flows, each an eco-agent: SCADA (priority 2) and
       telemetry (priority 1). The PLACES are the site's two access media. A medium
       uses capacity at its bottlenecks: the serving eNodeB's cell for private LTE,
       and every store-and-forward relay on the path for 900 MHz. There is also the
       PARKED place: the flow stops transmitting - always possible, never
       satisfying.

       * satisfied: on a medium with no stopped or degraded node, and within every
         bottleneck's capacity in priority order;
       * prevented: a bottleneck is full; only a flow of STRICTLY lower priority
         may be attacked, which rules out ping-pong between equals;
       * flight: to the other medium when it fits, or park;
       * dependency: a site's telemetry acts only once that site's SCADA flow is
         satisfied.

       The world state comes from the INCIDENTS the blackboard diagnosed, not from
       the commanded fault: an outage becomes a stopped node, interference a
       degraded node, congestion a reduced capacity. Capacities are nominal.

       A design difference from the blackboard: the arbiter decides per site; here
       each flow decides for itself, and a site's two flows may end on different
       media. The decision holds for both ends of the flow at once - which is what
       avoids the local-failover flapping seen in experiment 004.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, FrozenSet, Hashable, List, Mapping, Optional, Sequence, Set, Tuple

from aisg.domain.diagnoses import DIAGNOSES, EcoEffect
from aisg.domain.topology import Topology
from aisg.eco.engine import EcoAgent, EcoWorld, Ecosystem, Move

PARKED = "parked"
MEDIA = ("plte", "radio900")

#: NOMINAL, UNCALIBRATED capacities, in flows. A cell holds 6 flows: exactly
#: what the three busiest cells carry before any fault, so a failover onto them
#: must displace someone - the trade-off eco-resolution is meant to settle.
ECO_NETWORK_PARAMETERS: Dict[str, int] = {
    "cell_capacity_flows": 6,
    "congested_cell_capacity_flows": 2,
    "saf_capacity_flows": 12,
    "congested_saf_capacity_flows": 3,
}

#: (flow class, priority), highest priority first.
FLOW_CLASSES: Tuple[Tuple[str, int], ...] = (("scada", 2), ("telemetry", 1))

OUTAGE = tuple(
    name for name, contract in DIAGNOSES.items() if contract.eco_effect == EcoEffect.DOWN
)
DEGRADING = tuple(
    name for name, contract in DIAGNOSES.items() if contract.eco_effect == EcoEffect.DEGRADED
)
CONGESTED = tuple(
    name for name, contract in DIAGNOSES.items()
    if contract.eco_effect == EcoEffect.REDUCED_CAPACITY
)


@dataclass(frozen=True)
class SiteMedia:
    er: str
    primary: str
    #: medium -> every node the medium's path depends on
    path_nodes: Dict[str, Tuple[str, ...]]
    #: medium -> the capacity bottlenecks on that path
    resources: Dict[str, Tuple[str, ...]]


@dataclass(frozen=True)
class Flow:
    name: str
    site: str
    cls: str
    priority: int


class NetworkEcoWorld(EcoWorld):
    def __init__(
        self,
        sites: Mapping[str, SiteMedia],
        capacities: Mapping[str, int],
        flows: Sequence[Flow],
        *,
        down: FrozenSet[str] = frozenset(),
        degraded: FrozenSet[str] = frozenset(),
    ) -> None:
        self.sites = dict(sites)
        self.capacities = dict(capacities)
        self.flows = {f.name: f for f in flows}
        self.down = frozenset(down)
        self.degraded = frozenset(degraded)
        self.assignment: Dict[str, str] = {f.name: PARKED for f in flows}

    # -- queries -----------------------------------------------------------------
    def usable(self, site: str, medium: str) -> bool:
        nodes = self.sites[site].path_nodes[medium]
        return not (set(nodes) & (self.down | self.degraded))

    def resources(self, flow: str, medium: str) -> Tuple[str, ...]:
        if medium == PARKED:
            return ()
        return self.sites[self.flows[flow].site].resources[medium]

    def occupants(self, resource: str) -> List[str]:
        """Flows using a resource, in the order capacity is granted."""
        users = [
            name for name, medium in self.assignment.items()
            if medium != PARKED and resource in self.resources(name, medium)
        ]
        return sorted(users, key=lambda n: (-self.flows[n].priority, n))

    def within_capacity(self, flow: str) -> bool:
        medium = self.assignment[flow]
        for resource in self.resources(flow, medium):
            if self.occupants(resource).index(flow) >= self.capacities[resource]:
                return False
        return True

    def room_for(self, flow: str, medium: str) -> bool:
        """Whether ``flow`` could be granted capacity on ``medium`` once there."""
        for resource in self.resources(flow, medium):
            others = [o for o in self.occupants(resource) if o != flow]
            ahead = [o for o in others if self.flows[o].priority >= self.flows[flow].priority]
            if len(ahead) >= self.capacities[resource]:
                return False
        return True

    def describe(self) -> Dict[str, str]:
        return dict(sorted(self.assignment.items()))

    # -- EcoWorld --------------------------------------------------------------------
    def snapshot(self) -> Hashable:
        return tuple(sorted(self.assignment.items()))

    def apply(self, move: Move) -> None:
        flow, medium = move.agent, move.place
        if flow not in self.flows:
            raise ValueError(f"{flow} is not a flow")
        if medium != PARKED:
            if medium not in MEDIA:
                raise ValueError(f"{medium} is not a medium")
            if not self.usable(self.flows[flow].site, medium):
                raise ValueError(f"{medium} is not usable for {self.flows[flow].site}")
            for resource in self.resources(flow, medium):
                others = [o for o in self.occupants(resource) if o != flow]
                if len(others) >= self.capacities[resource]:
                    raise ValueError(f"{resource} is full")
        self.assignment[flow] = medium


class FlowAgent(EcoAgent):
    def __init__(self, flow: Flow, primary: str) -> None:
        super().__init__(flow.name)
        self.flow = flow
        self.primary = primary

    def _preferences(self) -> Tuple[str, ...]:
        return (self.primary,) + tuple(m for m in MEDIA if m != self.primary)

    def _reachable(self, world: NetworkEcoWorld, medium: str) -> bool:
        return world.usable(self.flow.site, medium) and world.room_for(self.name, medium)

    def dependencies(self, world: EcoWorld) -> Tuple[str, ...]:
        if self.flow.cls == "scada":
            return ()
        return (f"{self.flow.site}/scada",)

    def is_satisfied(self, world: EcoWorld, ecosystem: Ecosystem) -> bool:
        assert isinstance(world, NetworkEcoWorld)
        medium = world.assignment[self.name]
        return (
            medium != PARKED
            and world.usable(self.flow.site, medium)
            and world.within_capacity(self.name)
        )

    def satisfaction_move(self, world: EcoWorld) -> Optional[Move]:
        assert isinstance(world, NetworkEcoWorld)
        current = world.assignment[self.name]
        for medium in self._preferences():
            if medium != current and self._reachable(world, medium):
                return Move(self.name, medium)
        return None

    def blockers(self, world: EcoWorld, move: Move) -> List[str]:
        assert isinstance(world, NetworkEcoWorld)
        found = []
        for resource in world.resources(self.name, move.place):
            others = [o for o in world.occupants(resource) if o != self.name]
            if len(others) < world.capacities[resource]:
                continue
            weaker = [o for o in others if world.flows[o].priority < self.flow.priority]
            if weaker:
                # the weakest, most recently granted occupant yields first
                found.append(weaker[-1])
        return list(dict.fromkeys(found))

    def flight_moves(self, world: EcoWorld, constraints: FrozenSet[str]) -> List[Move]:
        assert isinstance(world, NetworkEcoWorld)
        current = world.assignment[self.name]
        moves = [
            Move(self.name, medium) for medium in self._preferences()
            if medium != current and medium not in constraints
            and self._reachable(world, medium)
        ]
        if current != PARKED:
            moves.append(Move(self.name, PARKED))
        return moves

    def goal_places(self, world: EcoWorld) -> FrozenSet[str]:
        move = self.satisfaction_move(world)
        return frozenset({move.place}) if move else frozenset()

    def position(self, world: EcoWorld) -> Hashable:
        assert isinstance(world, NetworkEcoWorld)
        return world.assignment[self.name]


@dataclass
class NetworkProblem:
    ecosystem: Ecosystem
    world: NetworkEcoWorld
    fault_scenario: Optional[str]
    down: FrozenSet[str] = frozenset()
    degraded: FrozenSet[str] = frozenset()
    congested: FrozenSet[str] = frozenset()
    initial: Dict[str, str] = field(default_factory=dict)


def network_ecosystem(
    topology: Topology,
    fault_scenario: Optional[str] = None,
    params: Optional[Mapping[str, int]] = None,
) -> NetworkProblem:
    """
    Build the flow ecosystem for a blackboard fault scenario.

    PT-BR: Os fluxos comecam onde estavam antes da falha - no meio primario de
           cada site, dentro da capacidade nominal - e a falha diagnosticada muda
           o mundo sob eles.
    EN:    Flows start where they were before the fault - on each site's primary
           medium, within nominal capacity - and the diagnosed fault changes the
           world under them.
    """
    from aisg.blackboard import Level, build_scenario, solve
    from aisg.search import shortest_route
    from aisg.simulation import build_ns3_scenario
    from aisg.simulation.ns3_scenario import ROLE_BY_KIND

    p = dict(ECO_NETWORK_PARAMETERS)
    p.update(params or {})
    exported = build_ns3_scenario(topology)
    roles = {n.id: ROLE_BY_KIND[n.kind] for n in topology.nodes.values()}
    noc = next(nid for nid, role in roles.items() if role == "noc")
    serving = dict(exported.attachments)
    lte_side = tuple(nid for nid, role in roles.items() if role in ("enb", "cpe"))

    sites: Dict[str, SiteMedia] = {}
    for site in exported.sites:
        radio_path = shortest_route(topology, noc, site.er, avoid=lte_side) or []
        enb = serving[site.cpe]
        sites[site.er] = SiteMedia(
            er=site.er,
            primary=site.primary,
            path_nodes={
                "radio900": tuple(radio_path[1:]),
                "plte": (site.cpe, enb, site.er),
            },
            resources={
                "radio900": tuple(n for n in radio_path if roles.get(n) == "saf"),
                "plte": (enb,),
            },
        )

    down: Set[str] = set()
    degraded: Set[str] = set()
    congested: Set[str] = set()
    if fault_scenario is not None:
        run = solve(build_scenario(fault_scenario, topology), topology)
        for incident in run.board.entries(Level.INCIDENT, key="incident"):
            if incident.value in OUTAGE:
                down.add(incident.subject)
            elif incident.value in DEGRADING:
                degraded.add(incident.subject)
            elif incident.value in CONGESTED:
                congested.add(incident.subject)

    nominal: Dict[str, int] = {}
    for nid, role in roles.items():
        if role == "enb":
            nominal[nid] = p["cell_capacity_flows"]
        elif role == "saf":
            nominal[nid] = p["saf_capacity_flows"]

    flows = [
        Flow(f"{er}/{cls}", er, cls, priority)
        for er in sorted(sites)
        for cls, priority in FLOW_CLASSES
    ]
    world = NetworkEcoWorld(sites, nominal, flows)
    # Pre-fault placement: every flow on its primary medium, within nominal capacity.
    for flow in sorted(flows, key=lambda f: (-f.priority, f.name)):
        world.apply(Move(flow.name, sites[flow.site].primary))
    initial = world.describe()
    # The diagnosed faults then change the world under the placed flows.
    world.down = frozenset(down)
    world.degraded = frozenset(degraded)
    for nid in congested:
        role = roles.get(nid)
        if role == "enb":
            world.capacities[nid] = p["congested_cell_capacity_flows"]
        elif role == "saf":
            world.capacities[nid] = p["congested_saf_capacity_flows"]

    agents = [
        FlowAgent(flow, sites[flow.site].primary)
        for flow in sorted(flows, key=lambda f: (-f.priority, f.name))
    ]
    return NetworkProblem(
        ecosystem=Ecosystem(world, agents),
        world=world,
        fault_scenario=fault_scenario,
        down=frozenset(down),
        degraded=frozenset(degraded),
        congested=frozenset(congested),
        initial=initial,
    )
