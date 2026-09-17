"""Shared domain model / Modelo de dominio compartilhado."""

from aisg.domain.diagnoses import (
    DIAGNOSES,
    DiagnosisContract,
    EcoEffect,
    FaultMechanism,
    RoutingEffect,
    SimulationCapability,
    SimulationSupport,
    diagnosis_contract,
)
from aisg.domain.topology import (
    BUNDLED_TOPOLOGIES,
    LINK_TYPES,
    MAX_SPEED_M_PER_MS,
    Link,
    LinkType,
    Node,
    Topology,
    TopologyError,
    load_default_topology,
    load_topology,
)

__all__ = [
    "BUNDLED_TOPOLOGIES",
    "DIAGNOSES",
    "LINK_TYPES",
    "MAX_SPEED_M_PER_MS",
    "DiagnosisContract",
    "EcoEffect",
    "FaultMechanism",
    "Link",
    "LinkType",
    "Node",
    "RoutingEffect",
    "SimulationCapability",
    "SimulationSupport",
    "Topology",
    "TopologyError",
    "diagnosis_contract",
    "load_default_topology",
    "load_topology",
]
