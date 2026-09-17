"""Shared diagnosis vocabulary and current component capabilities.

Induction recipes describe intended experiments, not implemented ns-3 support.
Unsupported effects are explicit gaps, never declarations that a node is healthy.
This module contains only domain data; it does not import decision components.
"""

from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType
from typing import Mapping, Optional


class RoutingEffect(str, Enum):
    NONE = "none"
    EXCLUDE = "exclude"
    AVOID_IF_POSSIBLE = "avoid_if_possible"
    UNSUPPORTED = "unsupported"


class EcoEffect(str, Enum):
    NONE = "none"
    DOWN = "down"
    DEGRADED = "degraded"
    REDUCED_CAPACITY = "reduced_capacity"
    UNSUPPORTED = "unsupported"


class SimulationSupport(str, Enum):
    SUPPORTED = "supported"
    APPROXIMATION = "approximation"
    UNSUPPORTED = "unsupported"
    BASELINE = "baseline"


class FaultMechanism(str, Enum):
    """
    Fault-injection mechanisms the ns-3 exporter implements.

    Closed on purpose. A mechanism named here but not dispatched by
    ``_add_faults`` raises; a mechanism absent from here cannot enter a
    contract at all. Before this was an enum, a plausible-looking string
    reached the exporter, matched no dispatch branch, and produced a
    fault-free scenario that was then "verified" against predictions
    expecting a fault.
    """

    NODE_DOWN = "node_down"
    RADIO_PER = "radio_per"
    FLOOD = "flood"


@dataclass(frozen=True)
class SimulationCapability:
    support: SimulationSupport
    mechanism: Optional[FaultMechanism]
    explanation: str

    def __post_init__(self) -> None:
        if self.mechanism is not None and not isinstance(self.mechanism, FaultMechanism):
            raise ValueError("mechanism must be a FaultMechanism member or None")
        executable = self.support in (
            SimulationSupport.SUPPORTED, SimulationSupport.APPROXIMATION
        )
        if executable != bool(self.mechanism):
            raise ValueError("Only supported or approximate faults have a mechanism")
        if not self.explanation.strip():
            raise ValueError("Simulation capabilities require an explanation")


@dataclass(frozen=True)
class DiagnosisContract:
    induction_recipe: str
    # None means no repair is needed (healthy), not an unsupported planner fault.
    planner_fault: Optional[str]
    correlates_as_outage: bool
    routing_effect: RoutingEffect
    eco_effect: EcoEffect
    simulation: SimulationCapability
    # Required whenever routing or eco-resolution does not handle this diagnosis.
    handling_gap: str = ""

    def __post_init__(self) -> None:
        if not self.induction_recipe.strip():
            raise ValueError("A diagnosis requires an induction recipe")
        unsupported = (
            self.routing_effect == RoutingEffect.UNSUPPORTED
            or self.eco_effect == EcoEffect.UNSUPPORTED
        )
        if unsupported and not self.handling_gap.strip():
            raise ValueError("Unsupported handling requires an explanation")


DIAGNOSES: Mapping[str, DiagnosisContract] = MappingProxyType({
    "rf_interference": DiagnosisContract(
        "add an emitter on the same channel, or overlap two sector channels",
        "interference", False, RoutingEffect.AVOID_IF_POSSIBLE, EcoEffect.DEGRADED,
        SimulationCapability(SimulationSupport.APPROXIMATION, FaultMechanism.RADIO_PER,
                             "Packet loss on radio links; no interfering emitter is modelled."),
    ),
    "excess_path_loss": DiagnosisContract(
        "raise the propagation loss exponent, extend the distance, or cut transmit power",
        "excess-path-loss", False, RoutingEffect.AVOID_IF_POSSIBLE, EcoEffect.DEGRADED,
        SimulationCapability(SimulationSupport.APPROXIMATION, FaultMechanism.RADIO_PER,
                             "Same packet-error injection as interference; causes are not distinguishable."),
    ),
    "mac_contention": DiagnosisContract(
        "add nodes to one PAN, or raise their offered load, so CSMA-CA backoff dominates",
        "mac-contention", False, RoutingEffect.AVOID_IF_POSSIBLE, EcoEffect.DEGRADED,
        SimulationCapability(SimulationSupport.UNSUPPORTED, None,
                             "The point-to-point radio abstraction has no contention-capable MAC."),
    ),
    "node_failure": DiagnosisContract(
        "stop the node's device or application mid-run",
        "node-stopped", True, RoutingEffect.EXCLUDE, EcoEffect.DOWN,
        SimulationCapability(SimulationSupport.SUPPORTED, FaultMechanism.NODE_DOWN,
                             "Uses the simulator's node-down mechanism."),
    ),
    "upstream_relay_failure": DiagnosisContract(
        "stop the store-and-forward relay serving the chain",
        "relay-down", True, RoutingEffect.EXCLUDE, EcoEffect.DOWN,
        SimulationCapability(SimulationSupport.SUPPORTED, FaultMechanism.NODE_DOWN,
                             "Uses node-down on the upstream relay."),
    ),
    "routing_misconfiguration": DiagnosisContract(
        # The node answers (rule S19 requires node_responding = yes) but forwards
        # nothing to the destination prefix. Routing must EXCLUDE rather than merely
        # avoid it: transit across it is black-holed, not slowed. Eco-resolution
        # records it as degraded rather than down for the same reason the rule
        # fires - the node is alive - and `usable` forbids the path either way.
        "remove or misdirect the route to the destination prefix",
        "route-missing", False, RoutingEffect.EXCLUDE, EcoEffect.DEGRADED,
        SimulationCapability(SimulationSupport.UNSUPPORTED, None,
                             "Route removal or misdirection is not implemented by the exporter."),
    ),
    "congestion": DiagnosisContract(
        "drive offered load beyond the link's capacity with a traffic generator",
        "congested", False, RoutingEffect.EXCLUDE, EcoEffect.REDUCED_CAPACITY,
        SimulationCapability(SimulationSupport.SUPPORTED, FaultMechanism.FLOOD,
                             "UDP flood; the exporter supports only eNodeB targets."),
    ),
    "healthy": DiagnosisContract(
        "baseline run: nominal propagation, one emitter, offered load within capacity",
        None, False, RoutingEffect.NONE, EcoEffect.NONE,
        SimulationCapability(SimulationSupport.BASELINE, None,
                             "Fault-free baseline; never emitted as a fault command."),
    ),
})


def diagnosis_contract(name: str) -> DiagnosisContract:
    """Look up a diagnosis, rejecting unknown names rather than treating them as healthy."""
    try:
        return DIAGNOSES[name]
    except KeyError:
        raise ValueError(f"Unknown diagnosis {name!r}; expected one of {', '.join(DIAGNOSES)}") from None
