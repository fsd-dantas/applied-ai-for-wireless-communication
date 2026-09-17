"""
Planning domain: restoring service on a node of the simulated scenario.

PT-BR: Este dominio e o ponto de encontro dos tres trabalhos. O DIAGNOSTICO vem do
       sistema especialista e vira o estado inicial; o PLANO e gerado por GPS ou por
       A* progressivo; e a acao 'desviar trafego' so e aplicavel quando a BUSCA A*
       sobre a topologia confirma que existe rota alternativa.

EN:    This domain is where the three assignments meet. The DIAGNOSIS comes from the
       expert system and becomes the initial state; the PLAN is produced by GPS or by
       A* progression; and the 'reroute traffic' action is applicable only when A*
       SEARCH over the topology confirms an alternative route exists.

Governance encoded as preconditions / Governanca como precondicao
-----------------------------------------------------------------
Every operator that changes the scenario requires ``authorized(?n)`` - directly,
or for ``start_run`` through the ``stop_run`` that must precede it. That is not
decoration: it makes "we acted without authorisation" *unreachable* rather than
merely discouraged. Only verifying, logging and closing skip it, because they
change nothing.
"""

from __future__ import annotations

from typing import Dict, Iterable, List, Optional, Sequence

from aisg.domain.diagnoses import DIAGNOSES
from aisg.domain.topology import Topology
from aisg.planning.strips import Operator, Predicate, Problem, make_state

#: Expert-system diagnosis -> the fault literal it puts in the initial state.
DIAGNOSIS_TO_FAULT: Dict[str, Optional[str]] = {
    name: contract.planner_fault for name, contract in DIAGNOSES.items()
}

#: Every fault the domain can repair. A fault outside this set would have no
#: operator able to clear it, and the planner would fail with no explanation.
KNOWN_FAULTS = frozenset(f for f in DIAGNOSIS_TO_FAULT.values() if f)

#: Node kinds that terminate operational traffic, in order of preference: the
#: 30-node scenario ends in field devices, the 60-node one in edge routers.
DESTINATION_KINDS = ("field_device", "edge_router")


def cleared(fault: str) -> str:
    """
    The literal asserting that one specific fault has been repaired.

    PT-BR: Um literal POR FALHA, e nao um sinalizador unico. Com um sinalizador
           compartilhado, reparar uma falha entre varias marcaria o no como
           verificavel enquanto as outras permanecem — e o plano fecharia a ordem
           de servico com o defeito ainda presente.
    EN:    One literal PER FAULT, not a single shared flag. With a shared flag,
           repairing one fault among several would mark the node verifiable while
           the others remain, and the plan would close the work order with the
           defect still in place.
    """
    return f"cleared-{fault}(?n)"


def build_operators(faults: Sequence[str] = ()) -> List[Operator]:
    """
    The thirteen restoration operators, in STRIPS form.

    ``faults`` are the fault names present in the problem being built. They
    determine what ``verify_link`` demands: the link counts as verified only once
    *every* fault diagnosed on it has its own ``cleared-…`` literal. STRIPS has no
    negative preconditions, so "no fault remains" is expressed as the conjunction
    of the specific repairs the instance requires.
    """
    build = Operator.build
    # A link is only verifiable with the run active again, which is what makes
    # stopping the run a cost rather than a free precaution.
    verify_preconditions = (
        ("diagnosed(?n)",) + tuple(cleared(f) for f in faults) + ("run-active(?n)",)
    )

    return [
        build(
            "request_authorization",
            parameters=("?n",),
            preconditions=("diagnosed(?n)",),
            add=("authorized(?n)",),
            cost=1.0,
            description_pt="Solicitar autorizacao e janela de manutencao para ?n.",
            description_en="Request authorisation and a maintenance window for ?n.",
        ),
        build(
            "change_channel",
            parameters=("?n",),
            preconditions=("authorized(?n)", "interference(?n)"),
            add=("cleared-interference(?n)",),
            delete=("interference(?n)",),
            cost=2.0,
            description_pt="Mudar o canal de ?n para sair da emissao interferente.",
            description_en="Change the channel of ?n to move away from the interferer.",
        ),
        build(
            "restore_relay",
            parameters=("?n",),
            preconditions=("authorized(?n)", "relay-down(?n)"),
            add=("cleared-relay-down(?n)",),
            delete=("relay-down(?n)",),
            cost=2.0,
            description_pt="Recuperar o repetidor a montante de ?n.",
            description_en="Recover the relay upstream of ?n.",
        ),
        build(
            "reroute_traffic",
            parameters=("?n",),
            preconditions=("authorized(?n)", "congested(?n)", "alternate-route(?n)"),
            add=("cleared-congested(?n)", "traffic-rerouted(?n)"),
            delete=("congested(?n)",),
            cost=2.0,
            description_pt="Desviar o trafego de ?n pela rota alternativa calculada por A*.",
            description_en="Reroute the traffic of ?n over the alternative route computed by A*.",
        ),
        # ---- the run -----------------------------------------------------
        # What costs here is the run itself. Changing a SCENARIO PARAMETER - the
        # propagation budget, the channel plan - invalidates the run in progress,
        # so the run must be stopped and restarted. Runtime repairs do not. That
        # is the real trade-off: batch the parameter changes into one restart,
        # or pay for another.
        build(
            "stop_run",
            parameters=("?n",),
            preconditions=("authorized(?n)", "run-active(?n)"),
            add=("run-stopped(?n)",),
            delete=("run-active(?n)",),
            cost=2.0,
            description_pt="Interromper a execucao de ?n para alterar parametros do cenario.",
            description_en="Stop the run at ?n to change scenario parameters.",
        ),
        build(
            "start_run",
            parameters=("?n",),
            preconditions=("run-stopped(?n)",),
            add=("run-active(?n)",),
            delete=("run-stopped(?n)",),
            cost=2.0,
            description_pt="Retomar a execucao de ?n.",
            description_en="Restart the run at ?n.",
        ),
        build(
            "restore_path_budget",
            parameters=("?n",),
            # A propagation parameter: the run in progress cannot absorb it.
            preconditions=("authorized(?n)", "excess-path-loss(?n)", "run-stopped(?n)"),
            add=(cleared("excess-path-loss"),),
            delete=("excess-path-loss(?n)",),
            cost=1.0,
            description_pt="Restaurar o orcamento de percurso de ?n no cenario.",
            description_en="Restore the scenario's path budget at ?n.",
        ),
        build(
            "separate_channels",
            parameters=("?n",),
            # A channel-plan change: also a scenario parameter.
            preconditions=("authorized(?n)", "mac-contention(?n)",
                           "run-stopped(?n)"),
            add=(cleared("mac-contention"),),
            delete=("mac-contention(?n)",),
            cost=3.0,
            description_pt="Separar os setores em frequencia no cenario de ?n.",
            description_en="Separate the sectors in frequency in the scenario at ?n.",
        ),
        build(
            "restart_node",
            parameters=("?n",),
            # A runtime event in the simulator: no parameter change, no restart.
            preconditions=("authorized(?n)", "node-stopped(?n)"),
            add=(cleared("node-stopped"),),
            delete=("node-stopped(?n)",),
            cost=1.0,
            description_pt="Reativar o no parado no cenario de ?n.",
            description_en="Restart the node stopped in the scenario at ?n.",
        ),
        build(
            "fix_routing",
            parameters=("?n",),
            preconditions=("authorized(?n)", "route-missing(?n)"),
            add=(cleared("route-missing"),),
            delete=("route-missing(?n)",),
            cost=1.0,
            description_pt="Corrigir a rota para o destino de ?n.",
            description_en="Correct the route to the destination at ?n.",
        ),
        build(
            "verify_link",
            parameters=("?n",),
            preconditions=verify_preconditions,
            add=("link-up(?n)",),
            cost=1.0,
            description_pt="Verificar o enlace de ?n apos a correcao.",
            description_en="Verify the link at ?n after the correction.",
        ),
        build(
            "record_logbook",
            parameters=("?n",),
            preconditions=("link-up(?n)",),
            add=("logged(?n)",),
            cost=1.0,
            description_pt="Registrar a intervencao em ?n no livro de registro.",
            description_en="Record the intervention on ?n in the logbook.",
        ),
        build(
            "close_work_order",
            parameters=("?n",),
            preconditions=("link-up(?n)", "logged(?n)"),
            add=("service-restored(?n)",),
            cost=1.0,
            description_pt="Encerrar a ordem de servico de ?n.",
            description_en="Close the work order for ?n.",
        ),
    ]


def build_restoration_problem(
    node: str,
    faults: Sequence[str],
    *,
    alternate_route: bool = False,
    extra_initial: Iterable[str] = (),
) -> Problem:
    """
    Build the STRIPS problem for restoring ``node``.

    :param faults: fault predicate names, e.g. ``["mac-contention"]``.
    :param alternate_route: whether A* confirmed an alternative route exists.
    """
    unknown = [f for f in faults if f not in KNOWN_FAULTS]
    if unknown:
        raise ValueError(
            f"unknown fault(s): {', '.join(unknown)}; expected one or more of "
            f"{', '.join(sorted(KNOWN_FAULTS))}"
        )

    initial: List[str] = [f"diagnosed({node})", f"run-active({node})"]
    initial += [f"{fault}({node})" for fault in faults]
    if alternate_route:
        initial.append(f"alternate-route({node})")
    initial += list(extra_initial)

    # With no faults the link needs only verification and closure: verify_link's
    # preconditions reduce to diagnosed(?n) and run-active(?n).
    return Problem(
        name=f"restore-service-{node}",
        operators=build_operators(faults),
        initial=make_state(initial),
        goal=make_state([f"service-restored({node})", f"logged({node})"]),
        objects={"node": [node]},
        parameter_types={"?n": "node"},
    )


def problem_from_diagnosis(
    diagnosis: str,
    node: str,
    *,
    topology: Optional[Topology] = None,
    reroute_target: Optional[str] = None,  # the destination, not the source
) -> Problem:
    """
    Turn an expert-system diagnosis into a planning problem.

    PT-BR: Quando o diagnostico e congestionamento, consultamos o A* sobre a topologia
           para saber se existe de fato rota alternativa evitando o no afetado. Se nao
           existir, a acao 'desviar trafego' fica inaplicavel e o planejador precisa
           encontrar outro caminho — ou falhar honestamente.
    EN:    When the diagnosis is congestion we consult A* over the topology to learn
           whether an alternative route avoiding the affected node really exists. If
           it does not, 'reroute traffic' is inapplicable and the planner must find
           another way — or fail honestly.
    """
    if diagnosis not in DIAGNOSIS_TO_FAULT:
        raise ValueError(
            f"unknown diagnosis {diagnosis!r}; expected one of "
            f"{', '.join(sorted(DIAGNOSIS_TO_FAULT))}"
        )

    fault = DIAGNOSIS_TO_FAULT[diagnosis]
    faults = [fault] if fault else []

    alternate = False
    if fault == "congested" and topology is not None:
        from aisg.search.graph_problem import shortest_route

        # `reroute_target` names the DESTINATION whose traffic is being diverted,
        # not the source. Using it as the source silently checked a different
        # route from the one the caller asked about.
        source = _default_source(topology)
        target = reroute_target or _default_target(topology, node)
        if target is not None and target != node:
            alternate = shortest_route(topology, source, target, avoid=(node,)) is not None

    return build_restoration_problem(node, faults, alternate_route=alternate)


def _default_source(topology: Topology) -> str:
    """The operations centre, if the topology declares one."""
    for node in topology.nodes.values():
        if node.kind == "control_centre":
            return node.id
    return next(iter(topology.nodes))


def _default_target(topology: Topology, node: str) -> Optional[str]:
    """
    A node whose traffic the congested node carries.

    PT-BR: Usamos como destino do desvio o primeiro no onde o trafego termina: um
           dispositivo de campo ou, no cenario de 60 nos, um roteador de borda.
    EN:    We use the first node where traffic ends as the reroute destination: a
           field device or, in the 60-node scenario, an edge router.
    """
    for kind in DESTINATION_KINDS:
        for candidate in topology.nodes.values():
            if candidate.kind == kind and candidate.id != node:
                return candidate.id
    return None


def fault_literals(problem: Problem) -> List[Predicate]:
    """The fault literals present in a problem's initial state, for reporting."""
    fault_names = {name for name in DIAGNOSIS_TO_FAULT.values() if name}
    return sorted(
        (p for p in problem.initial if p.name in fault_names), key=str
    )
