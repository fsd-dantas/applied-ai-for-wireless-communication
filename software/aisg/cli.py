"""
Command-line interface / Interface de linha de comando.

PT-BR: Cinco subcomandos: ``diagnose`` (sistema especialista), ``plan``
       (planejamento STRIPS/GPS/A*), ``route`` (busca A*), ``pipeline``, que executa
       os tres em sequencia sobre o mesmo incidente, e ``blackboard``, o sistema
       multiespecialista sobre a rede inteira.

EN:    Five subcommands: ``diagnose`` (expert system), ``plan`` (STRIPS/GPS/A*
       planning), ``route`` (A* search), ``pipeline``, which runs all three in
       sequence over the same incident, and ``blackboard``, the multi-expert system
       over the whole network.

    python -m aisg diagnose --case rf_interference --trace
    python -m aisg diagnose --interactive --mode backward
    python -m aisg route --from NOC --to ER_03 --compare
    python -m aisg plan --diagnosis mac_contention --node ER_03 --solver both
    python -m aisg pipeline --case congestion --node SAF_01 --target ER_03
    python -m aisg blackboard --scenario dual-outage --experts --explain ER_03
    python -m aisg eco --problem blocks --sweep
    python -m aisg eco --problem network --scenario saf-chain-outage --trace
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path
from typing import Optional, Sequence, Tuple

from aisg import __version__
from aisg.blackboard import (
    SCENARIOS,
    Blackboard,
    Controller,
    Level,
    TaskGenerator,
    build_experts,
    build_scenario,
    medium_label,
)
from aisg.domain import BUNDLED_TOPOLOGIES, load_topology
from aisg.eco import (
    COURSE_EXAMPLE,
    BlocksWorld,
    blocks_ecosystem,
    enumerate_configurations,
    network_ecosystem,
)
from aisg.expert_system import (
    SIM_CASES,
    ConflictResolution,
    Consultation,
    InferenceEngine,
    Variable,
    VariableKind,
    build_simulated_knowledge_base,
)
from aisg.i18n import t
from aisg.observation import Observation, ObservationError
from aisg.planning import (
    fault_literals,
    format_state,
    plan_with_astar,
    plan_with_gps,
    problem_from_diagnosis,
)
from aisg.planning.domain_restoration import DESTINATION_KINDS
from aisg.search import RoutingProblem, astar, compare
from aisg.search.algorithms import SearchResult
from aisg.simulation import (
    ScenarioError,
    TelemetryError,
    build_ns3_scenario,
    diagnose_run,
    observations_from_run,
    score_against_commanded,
)

RULE = "=" * 78
THIN = "-" * 78


def _header(text: str) -> str:
    return f"\n{RULE}\n{text}\n{RULE}"


def _first_of_kind(topology, kind: str) -> Optional[str]:
    return next((n.id for n in topology.nodes.values() if n.kind == kind), None)


def _default_source(topology) -> str:
    """The operations centre, or any node if the scenario declares none."""
    return _first_of_kind(topology, "control_centre") or next(iter(topology.nodes))


def _default_target(topology, exclude: Optional[str] = None) -> str:
    """
    Where operational traffic ends: a field device, or else an edge router.

    PT-BR: Resolvido a partir da topologia, e nao fixado no codigo, para que os
           comandos funcionem em qualquer cenario carregado com --topology.
    EN:    Resolved from the topology rather than hard-coded, so the commands work on
           whichever scenario --topology loaded.
    """
    for kind in DESTINATION_KINDS:
        for node in topology.nodes.values():
            if node.kind == kind and node.id != exclude:
                return node.id
    return next(n for n in topology.nodes if n != exclude)


def _default_repair_node(topology) -> str:
    """A store-and-forward relay makes the most interesting restoration case."""
    return (
        _first_of_kind(topology, "saf_relay")
        or _first_of_kind(topology, "remote_radio")
        or next(iter(topology.nodes))
    )


# ---------------------------------------------------------------------------
# expert system
# ---------------------------------------------------------------------------
def _make_asker(lang: str, engine_holder: dict):
    """Build the interactive question callback for backward chaining."""

    def ask(variable: Variable, _why_stack) -> Optional[Tuple[object, float]]:
        engine = engine_holder.get("engine")
        while True:
            print()
            print(variable.prompt(lang))
            if variable.kind is VariableKind.NUMERIC:
                lo, hi = variable.bounds or (None, None)
                hint = f"  [{lo}, {hi}] {variable.unit}".rstrip()
            else:
                hint = "  " + " | ".join(variable.labels)
            print(f"{hint}   {t('value_unknown_hint', lang)}  ('?' = why / por que)")
            raw = input("> ").strip()

            if raw == "":
                return None
            if raw == "?":
                print()
                print(t("es_why", lang))
                if engine is not None:
                    print(engine.why(lang))
                continue

            # An optional trailing certainty: "many 0.6"
            cf = 1.0
            parts = raw.rsplit(" ", 1)
            if len(parts) == 2:
                try:
                    candidate = float(parts[1])
                except ValueError:
                    pass
                else:
                    if -1.0 <= candidate <= 1.0:
                        raw, cf = parts[0].strip(), candidate

            if variable.kind is VariableKind.NUMERIC:
                try:
                    value: object = float(raw)
                except ValueError:
                    print(t("invalid_option", lang))
                    continue
            else:
                value = raw
            try:
                variable.validate_value(value)
            except ValueError as exc:
                print(f"{t('invalid_option', lang)} ({exc})")
                continue
            return value, cf

    return ask


def _report_consultation(consultation: Consultation, lang: str, *, show_trace: bool,
                         show_explanation: bool) -> None:
    kb = consultation.kb

    if show_trace:
        print(_header(f"TRACE ({consultation.strategy})"))
        print(consultation.render_trace())

    print(_header(t("es_conclusion", lang)))
    conclusions = consultation.conclusions()
    if not conclusions:
        print(t("es_no_conclusion", lang))
    else:
        for goal, facts in conclusions.items():
            variable = kb.variables[goal]
            print(f"\n{variable.label(lang)}:")
            for fact in facts:
                bar = "#" * max(0, int(round(abs(fact.cf) * 20)))
                sign = " " if fact.cf >= 0 else "-"
                print(f"  {str(fact.value):<26} CF {fact.cf:+.2f} {sign}{bar}")

    if show_explanation and conclusions:
        print(_header(t("es_how", lang)))
        for goal, facts in conclusions.items():
            print(consultation.how(goal, facts[0].value, lang))
            print()

    print(THIN)
    print(kb.validity_note(lang))
    print(THIN)


def cmd_diagnose(args: argparse.Namespace) -> int:
    lang = args.lang
    kb = build_simulated_knowledge_base()
    cases = SIM_CASES
    holder: dict = {}
    engine = InferenceEngine(
        kb,
        ask=_make_asker(lang, holder) if args.interactive else None,
        strategy=ConflictResolution(args.strategy),
    )
    holder["engine"] = engine

    print(_header(f"{t('es_title', lang)}  [{kb.name(lang)}]"))

    if args.from_observation or args.from_prometheus:
        try:
            if args.from_prometheus:
                from aisg.prometheus import (
                    PrometheusClient,
                    fetch_observation,
                    load_specs,
                )

                if not args.subject:
                    print("--from-prometheus needs --subject (the link or node id)")
                    return 2
                client = PrometheusClient(args.from_prometheus)
                specs = load_specs(args.specs) if args.specs else ()
                record = fetch_observation(client, args.subject, specs)
                if args.save_observation:
                    record.save(args.save_observation)
                    print(f"saved {args.save_observation}")
            else:
                record = Observation.load(args.from_observation)
            print(record.report(kb, lang))
            print()
            applied = record.apply_to(engine)
            print(f"{applied} " + ("fatos carregados" if lang == "pt"
                                   else "facts loaded"))
        except (ObservationError, OSError) as exc:
            print(exc)
            return 2
    elif args.case:
        if args.case not in cases:
            print(f"unknown case: {args.case}; available: {', '.join(sorted(cases))}")
            return 2
        for variable, value in cases[args.case].items():
            engine.given(variable, value)
        print(f"{t('es_known_facts', lang)}: {args.case}")
        for fact in engine.memory.all_facts():
            print(f"  {fact.render(kb, lang)}")
    elif not args.interactive:
        print(
            "Use --case NAME, --from-observation FILE, --from-prometheus URL, "
            "or --interactive."
        )
        return 2

    mode_label = t("es_backward" if args.mode == "backward" else "es_forward", lang)
    print(f"\n[{mode_label}]")

    if args.mode == "backward":
        consultation = engine.backward_chain(args.goal)
    else:
        consultation = engine.forward_chain()

    _report_consultation(
        consultation, lang, show_trace=args.trace, show_explanation=args.explain
    )
    return 0


# ---------------------------------------------------------------------------
# routing
# ---------------------------------------------------------------------------
def _print_search_result(result: SearchResult, problem: RoutingProblem, lang: str,
                         *, show_expansion: bool) -> None:
    print(result.describe(lang))
    if show_expansion and result.expansion_order:
        order = " ".join(str(s) for s in result.expansion_order)
        label = "ordem de expansao" if lang == "pt" else "expansion order"
        print(f"  {label}: {order}")


def cmd_route(args: argparse.Namespace) -> int:
    lang = args.lang
    topology = load_topology(getattr(args, "topology", "dual"))

    for spec in args.disable_link or []:
        try:
            a, b = spec.split("-", 1)
            topology.disable_link(a, b)
        except (ValueError, KeyError) as exc:
            print(f"--disable-link {spec}: {exc}")
            return 2

    print(_header(t("se_title", lang)))
    print(topology.summary(lang))

    source = args.source or _default_source(topology)
    target = args.target or _default_target(topology)
    try:
        problem = RoutingProblem(topology, source, target, tuple(args.avoid or ()))
    except (KeyError, ValueError) as exc:
        print(exc)
        return 2

    print()
    if args.compare:
        for result in compare(problem, problem.heuristic()):
            _print_search_result(result, problem, lang, show_expansion=args.expansion)
            print()
        return 0

    result = astar(problem, problem.heuristic())
    if not result.found:
        print(t("se_no_path", lang, start=source, goal=target))
        return 1
    _print_search_result(result, problem, lang, show_expansion=args.expansion)
    print()
    print(problem.explain_path(result.path, lang))
    return 0


# ---------------------------------------------------------------------------
# planning
# ---------------------------------------------------------------------------
def _report_plan(plan, lang: str, *, label: str) -> None:
    print(f"\n[{label}]")
    if plan is None:
        print(t("pl_no_plan", lang))
        return
    print(t("pl_plan_found", lang, n=plan.length))
    print(plan.render(lang))
    ok, reason = plan.validate()
    print(t("pl_validation_ok", lang) if ok else t("pl_validation_fail", lang, reason=reason))
    if plan.stats:
        stats = ", ".join(f"{k}={v:g}" for k, v in sorted(plan.stats.items()))
        print(f"  ({stats})")


def cmd_plan(args: argparse.Namespace) -> int:
    lang = args.lang
    topology = load_topology(getattr(args, "topology", "dual"))
    node = args.node or _default_repair_node(topology)
    try:
        problem = problem_from_diagnosis(args.diagnosis, node, topology=topology)
    except (ValueError, KeyError) as exc:
        print(exc)
        return 2

    print(_header(t("pl_title", lang)))
    print(f"{t('pl_initial_state', lang)}:")
    print(format_state(problem.initial))
    print(f"\n{t('pl_goal_state', lang)}:")
    print(format_state(problem.goal))
    faults = fault_literals(problem)
    if faults:
        label = "falha diagnosticada" if lang == "pt" else "diagnosed fault"
        print(f"\n{label}: {', '.join(str(f) for f in faults)}")

    if args.solver in ("gps", "both"):
        plan, trace = plan_with_gps(problem, lang=lang)
        if args.trace:
            print(_header("GPS — means-ends analysis trace"))
            print(trace.render())
        _report_plan(plan, lang, label="GPS (means-ends analysis)")

    if args.solver in ("astar", "both"):
        plan, result = plan_with_astar(problem, heuristic=args.heuristic)
        _report_plan(plan, lang, label=result.algorithm)

    return 0


# ---------------------------------------------------------------------------
# pipeline: expert system -> planner -> A*
# ---------------------------------------------------------------------------
def cmd_pipeline(args: argparse.Namespace) -> int:
    lang = args.lang
    topology = load_topology(getattr(args, "topology", "dual"))
    kb = build_simulated_knowledge_base()

    if args.case not in SIM_CASES:
        print(f"unknown case: {args.case}; available: {', '.join(sorted(SIM_CASES))}")
        return 2

    # --- 1. diagnose -----------------------------------------------------
    print(_header(f"1/3  {t('es_title', lang)}"))
    engine = InferenceEngine(kb)
    for variable, value in SIM_CASES[args.case].items():
        engine.given(variable, value)
    consultation = engine.forward_chain()
    conclusions = consultation.conclusions()
    if "diagnosis" not in conclusions:
        print(t("es_no_conclusion", lang))
        return 1

    diagnosis = conclusions["diagnosis"][0]
    action = conclusions.get("recommended_action", [None])[0]
    print(f"  {kb.variables['diagnosis'].label(lang)}: "
          f"{diagnosis.value} (CF {diagnosis.cf:+.2f})")
    if action is not None:
        print(f"  {kb.variables['recommended_action'].label(lang)}: "
              f"{action.value} (CF {action.cf:+.2f})")

    # --- 2. plan ---------------------------------------------------------
    print(_header(f"2/3  {t('pl_title', lang)}"))
    node = args.node or _default_repair_node(topology)
    # The planner must validate the SAME destination the route step will show.
    # Letting it fall back to its own default meant a plan could certify a
    # reroute towards one device while the demonstration routed to another -
    # and could report service restored for a destination that is unreachable.
    target = args.target or _default_target(topology, exclude=node)
    problem = problem_from_diagnosis(
        str(diagnosis.value), node, topology=topology, reroute_target=target
    )
    plan, result = plan_with_astar(problem)
    _report_plan(plan, lang, label=result.algorithm)

    # --- 3. route --------------------------------------------------------
    print(_header(f"3/3  {t('se_title', lang)}"))
    reroute = plan is not None and any(
        a.operator.name == "reroute_traffic" for a in plan.actions
    )
    source = _default_source(topology)

    avoid = (node,) if reroute else ()
    if reroute:
        note = (f"O plano inclui desviar trafego: recalculando a rota evitando {node}."
                if lang == "pt"
                else f"The plan includes rerouting: recomputing the route avoiding {node}.")
        print(note)
    try:
        routing = RoutingProblem(topology, source, target, avoid)
    except ValueError as exc:
        print(exc)
        return 0
    search = astar(routing, routing.heuristic())
    if not search.found:
        print(t("se_no_path", lang, start=source, goal=target))
        return 1
    print(search.describe(lang))
    print()
    print(routing.explain_path(search.path, lang))
    return 0


# ---------------------------------------------------------------------------
# blackboard: multi-expert restoration over the whole network
# ---------------------------------------------------------------------------
def _levels(levels) -> str:
    return ",".join(f"L{int(level)}" for level in levels)


def cmd_blackboard(args: argparse.Namespace) -> int:
    lang = args.lang
    pt = lang == "pt"
    topology = load_topology(getattr(args, "topology", "dual"))

    if args.list:
        for name in sorted(SCENARIOS):
            print(f"  {name:<20} {build_scenario(name, topology).title(lang)}")
        return 0
    try:
        scenario = build_scenario(args.scenario, topology)
    except KeyError as exc:
        print(exc.args[0])
        return 2

    experts = build_experts(topology)
    print(_header(
        ("Quadro-negro multiespecialista: " if pt else "Multi-expert blackboard: ")
        + scenario.title(lang)
    ))
    if args.experts:
        print("Especialistas (le -> escreve)" if pt else "Experts (reads -> writes)")
        for expert in sorted(experts, key=lambda s: (s.priority, s.name)):
            print(f"  {expert.name:<13} {_levels(expert.reads):>6} -> {_levels(expert.writes):<6}"
                  f" {expert.expertise(lang)}")
        print()

    board = Blackboard()
    posted = TaskGenerator(board).post(scenario.observations)
    print(f"{posted} observacoes postadas pelo gerador de tarefas" if pt
          else f"{posted} observations posted by the task generator")
    run = Controller(board, experts).loop()

    print(_header("Controlador" if pt else "Controller"))
    for record in run.records:
        line = f"  {'ciclo' if pt else 'cycle'} {record.cycle:>2}  {record.source:<13}" \
               f" +{record.added:<4} -{record.removed:<3}"
        if len(record.agenda) > 1:
            line += f" agenda: {' > '.join(record.agenda)}"
        print(line)
        if args.trace:
            for cycle, change, entry in board.history:
                if cycle == record.cycle and change == "add" and entry.level >= Level.INCIDENT:
                    print(f"        + {entry.render()}")
    if run.quiescent:
        print(f"  quiescencia apos {run.cycles} ciclos" if pt
              else f"  quiescence after {run.cycles} cycles")
    else:
        print(f"  LIMITE atingido apos {run.cycles} ciclos" if pt
              else f"  LIMIT reached after {run.cycles} cycles")

    print(_header("Incidentes" if pt else "Incidents"))
    incidents = sorted(board.entries(Level.INCIDENT), key=lambda e: (-e.cf, e.subject))
    if not incidents:
        print("  nenhum" if pt else "  none")
    for incident in incidents:
        explains = incident.data["explains"]
        print(f"  {incident.subject:<9} {incident.value:<24} CF {incident.cf:+.2f}  "
              f"{incident.data['kind']}" + (f", {len(explains)}: {', '.join(explains)}" if explains else ""))
        print(f"            {incident.rationale(lang)}")

    decisions = sorted(board.entries(Level.ACCESS, key="decision"), key=lambda e: e.subject)
    if decisions:
        print(_header("Acesso multi-RAT" if pt else "Multi-RAT access"))
        routes = {e.subject: e for e in board.entries(Level.ACCESS, key="route")}
        for decision in decisions:
            route = routes[decision.subject]
            print(f"  {decision.subject:<6} {decision.value:<16} {decision.rationale(lang)}")
            if route.value == "restored":
                print(f"         {' -> '.join(route.data['path'])}  "
                      f"({medium_label(route.data['medium'], lang)}, "
                      f"{route.data['cost_ms']:.1f} ms, A* {route.data['expanded']} "
                      f"{'expandidos' if pt else 'expanded'})")

    print(_header("Planos, por prioridade" if pt else "Plans, by priority"))
    for plan in sorted(board.entries(Level.PLAN), key=lambda e: e.data["priority"]):
        status = ("valido" if pt else "valid") if plan.data["valid"] else plan.data["invalid_reason"]
        print(f"  {plan.data['priority']}. {plan.subject} ({plan.data['diagnosis']}): "
              f"{' -> '.join(plan.data['actions'])}")
        print(f"     {'custo' if pt else 'cost'} {plan.data['cost']:g}, {status}. {plan.rationale(lang)}")

    print(_header(
        "Verdade comandada (so para avaliar; nenhum especialista a le)" if pt
        else "Commanded ground truth (scoring only; no expert reads it)"
    ))
    found = {(e.subject, e.value) for e in incidents}
    for node, diagnosis in sorted(scenario.commanded.items()):
        hit = (node, diagnosis) in found
        print(f"  {node:<9} {diagnosis:<24} "
              + (("encontrado" if pt else "found") if hit else ("NAO encontrado" if pt else "NOT found")))
    spurious = sorted(s for s, _v in found if s not in scenario.commanded)
    if spurious:
        print(f"  {'incidentes sem falha comandada' if pt else 'incidents with no commanded fault'}: "
              f"{', '.join(spurious)}")

    if args.explain:
        print(_header(f"{'Justificativas para' if pt else 'Justifications for'} {args.explain}"))
        entries = [e for e in board.entries(subject=args.explain) if e.level >= Level.SYMPTOM]
        if not entries:
            print("  sem conclusoes" if pt else "  no conclusions")
        for entry in sorted(entries, key=lambda e: (e.level, e.key, -e.cf)):
            print(f"  {entry.render()}")
            for line in entry.rationale(lang).splitlines():
                print(f"      {line}")

    return 0 if run.quiescent else 1


# ---------------------------------------------------------------------------
# eco-resolution
# ---------------------------------------------------------------------------
def _eco_verdict(result, pt: bool) -> None:
    status = ("convergiu" if pt else "converged") if result.converged else (
        "nao convergiu" if pt else "did not converge")
    print(f"  {status}: {result.reason}")
    print(f"  {'movimentos' if pt else 'moves'}: {result.steps}, "
          f"{'rodadas' if pt else 'rounds'}: {result.rounds}")
    if result.unsatisfied:
        print(f"  {'insatisfeitos' if pt else 'unsatisfied'}: {', '.join(result.unsatisfied)}")


def _eco_sweep(lang: str) -> int:
    pt = lang == "pt"
    tables = ("T1", "T2", "T3")
    configurations = enumerate_configurations(("A", "B", "C"), tables)
    reasons: Counter = Counter()
    lengths: Counter = Counter()
    for initial in configurations:
        for goal in configurations:
            result = blocks_ecosystem(tables, initial, goal).solve()
            reasons[result.reason] += 1
            if result.converged:
                lengths[result.steps] += 1
    total = len(configurations) ** 2
    print(_header(
        f"Convergencia: {len(configurations)} estados iniciais x {len(configurations)} objetivos"
        if pt else
        f"Convergence: {len(configurations)} initial states x {len(configurations)} goals"
    ))
    for reason, count in reasons.most_common():
        print(f"  {reason:<32} {count:>5}  ({100 * count / total:.1f}%)")
    converged = sum(lengths.values())
    if converged:
        mean = sum(k * n for k, n in lengths.items()) / converged
        print(f"  {'movimentos (convergidos)' if pt else 'moves (converged)'}: "
              f"{'media' if pt else 'mean'} {mean:.2f}, max {max(lengths)}")
        for steps in sorted(lengths):
            print(f"    {steps:>2} {'#' * max(1, lengths[steps] // 20)} {lengths[steps]}")
    return 0 if converged == total else 1


def cmd_eco(args: argparse.Namespace) -> int:
    lang = args.lang
    pt = lang == "pt"
    if args.problem == "blocks":
        if args.sweep:
            return _eco_sweep(lang)
        tables, initial, goal = COURSE_EXAMPLE
        ecosystem = blocks_ecosystem(tables, initial, goal)
        print(_header("Eco-resolucao: mundo dos blocos (exemplo da aula)" if pt
                      else "Eco-resolution: Blocks World (course example)"))
        print(f"  {'inicial ' if pt else 'initial '}: {BlocksWorld(tables, initial).render()}")
        print(f"  {'objetivo' if pt else 'goal    '}: {BlocksWorld(tables, goal).render()}")
        result = ecosystem.solve()
        print(_header("Rastro" if pt else "Trace"))
        for entry in result.trace:
            print(entry.render(lang))
        print(_header("Resultado" if pt else "Result"))
        print(f"  final   : {ecosystem.world.render()}")
        print(f"  {'sequencia' if pt else 'sequence '}: {' ; '.join(str(m) for m in result.moves)}")
        _eco_verdict(result, pt)
        return 0 if result.converged else 1

    problem = network_ecosystem(load_topology(getattr(args, "topology", "dual")), args.scenario)
    result = problem.ecosystem.solve()
    print(_header(
        (f"Eco-resolucao na rede: {args.scenario}" if pt else f"Eco-resolution on the network: {args.scenario}")
    ))
    print(f"  {'nos parados' if pt else 'stopped nodes'}: {', '.join(sorted(problem.down)) or '-'}")
    print(f"  {'nos degradados' if pt else 'degraded nodes'}: {', '.join(sorted(problem.degraded)) or '-'}")
    print(f"  {'congestionados' if pt else 'congested'}: {', '.join(sorted(problem.congested)) or '-'}")
    print(f"  {len(problem.world.flows)} {'fluxos (SCADA prioridade 2, telemetria 1)' if pt else 'flows (SCADA priority 2, telemetry 1)'}")
    if args.trace:
        print(_header("Rastro" if pt else "Trace"))
        for entry in result.trace:
            print(entry.render(lang))
    print(_header("Mudancas" if pt else "Changes"))
    changed = [
        (flow, problem.initial[flow], medium)
        for flow, medium in problem.world.assignment.items()
        if problem.initial[flow] != medium
    ]
    if not changed:
        print("  nenhuma" if pt else "  none")
    for flow, before, after in changed:
        print(f"  {flow:<16} {before:>9} -> {after}")
    print(_header("Resultado" if pt else "Result"))
    _eco_verdict(result, pt)
    return 0


# ---------------------------------------------------------------------------
# ns-3 export
# ---------------------------------------------------------------------------
def cmd_ns3_export(args: argparse.Namespace) -> int:
    pt = args.lang == "pt"
    topology = load_topology(getattr(args, "topology", "dual"))
    overrides = {}
    if args.sim_time is not None:
        overrides["sim_time_s"] = args.sim_time
    try:
        scenario = build_ns3_scenario(topology, overrides, fault_scenario=args.fault_scenario)
    except ScenarioError as exc:
        print(exc)
        return 2
    if not args.out:
        sys.stdout.write(scenario.render())
        return 0
    scenario.write(args.out)
    primaries = {}
    for site in scenario.sites:
        primaries[site.primary] = primaries.get(site.primary, 0) + 1
    media = ", ".join(f"{medium_label(m, args.lang)}: {n}" for m, n in sorted(primaries.items()))
    print(f"{'cenario ns-3 gravado em' if pt else 'ns-3 scenario written to'} {args.out}")
    print(f"  {len(scenario.nodes)} {'nos' if pt else 'nodes'}, "
          f"{len(scenario.links)} {'enlaces ponto a ponto' if pt else 'point-to-point links'}, "
          f"{len(scenario.attachments)} {'CPEs em LTE' if pt else 'LTE CPEs'}, "
          f"{len(scenario.sites)} sites")
    print(f"  {'meio primario' if pt else 'primary medium'}: {media}")
    for note in scenario.notes:
        print(f"  - {note}")
    if scenario.fault_scenario:
        print(f"  {'falhas' if pt else 'faults'} ({scenario.fault_scenario}): "
              + ", ".join(f"{kind} {target} @ {t:g}s" for t, kind, target, _ in scenario.faults))
        print(f"  {'failover central' if pt else 'central failover'}: "
              + (", ".join(f"{er} -> {medium_label(m, args.lang)} @ {t:g}s"
                           for t, er, m in scenario.failovers) or ("nenhum" if pt else "none")))
    return 0


# ---------------------------------------------------------------------------
# ns-3 telemetry -> observation records -> blackboard
# ---------------------------------------------------------------------------
def cmd_ns3_diagnose(args: argparse.Namespace) -> int:
    pt = args.lang == "pt"
    topology = load_topology(getattr(args, "topology", "dual"))
    kb = build_simulated_knowledge_base()
    try:
        observations = observations_from_run(args.results, topology)
    except TelemetryError as exc:
        print(exc)
        return 2

    print(_header(
        f"Diagnostico a partir da telemetria simulada: {args.results}" if pt
        else f"Diagnosis from simulated telemetry: {args.results}"
    ))
    askable = sum(1 for v in kb.variables.values() if v.askable)
    measured = sorted({name for record in observations for name in record.values})
    print(f"  {len(observations)} "
          + ("registros de observacao" if pt else "observation records")
          + f", {'janela' if pt else 'window'} {observations[0].window}, "
          + f"{'fonte' if pt else 'source'} {observations[0].source}")
    print(f"  {len(measured)}/{askable} "
          + ("variaveis medidas" if pt else "askable variables measured")
          + f": {', '.join(measured)}")
    silent = [
        record.subject_id for record in observations
        if record.values.get("node_responding", ("yes", 1.0))[0] == "no"
    ]
    print(f"  {'sem resposta' if pt else 'not responding'} ({len(silent)}): "
          f"{', '.join(silent) or '-'}")

    if args.save_observations:
        out = Path(args.save_observations)
        out.mkdir(parents=True, exist_ok=True)
        for record in observations:
            record.save(out / f"{record.subject_id}.json")
        print(f"  {'gravados em' if pt else 'saved to'} {out}")

    if args.unavailable:
        # Named, not presented as global: most reasons hold for every node, but
        # the upstream hop is particular to the node whose record this is.
        sample = observations[0]
        print(_header(
            f"Evidencia indisponivel em {sample.subject_id}, com o motivo" if pt
            else f"Unavailable evidence for {sample.subject_id}, with the reason"
        ))
        for variable, reason in sorted(sample.unavailable.items()):
            print(f"  {variable:<24} {reason}")
        print("  " + ("O salto a montante e por no; os demais motivos valem para todos."
                      if pt else
                      "The upstream hop is per node; the other reasons hold for every node."))

    run = diagnose_run(args.results, topology)
    print(_header("Incidentes" if pt else "Incidents"))
    incidents = sorted(
        run.board.entries(Level.INCIDENT, key="incident"),
        key=lambda e: (-e.cf, e.subject),
    )
    if not incidents:
        print("  nenhum" if pt else "  none")
    for incident in incidents:
        explains = incident.data.get("explains", [])
        suffix = (f", {len(explains)} " + ("explicados" if pt else "explained")) if explains else ""
        print(f"  {incident.subject:<9} {incident.value:<24} CF {incident.cf:+.2f}  "
              f"{incident.data['kind']}{suffix}")
        print(f"            {incident.rationale(args.lang)}")

    if not args.fault_scenario:
        return 0 if run.quiescent else 1

    # The only place the commanded fault is read. The adapter never opens
    # events.csv, and no expert is given the scenario.
    commanded = build_scenario(args.fault_scenario, topology).commanded
    score = score_against_commanded(run, commanded)
    print(_header(
        "Verdade comandada (so para avaliar; a telemetria nao a contem)" if pt
        else "Commanded ground truth (scoring only; the telemetry does not carry it)"
    ))
    for node, diagnosis in score.commanded:
        hit = (node, diagnosis) in score.hits
        print(f"  {node:<9} {diagnosis:<24} "
              + (("encontrado" if pt else "found") if hit
                 else ("NAO encontrado" if pt else "NOT found")))
    if score.spurious:
        print(f"  {'incidentes sem falha comandada' if pt else 'incidents with no commanded fault'}: "
              + ", ".join(f"{n}:{v}" for n, v in score.spurious))
    return 0 if score.exact else 1


# ---------------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="aisg",
        description=(
            "AI for smart grids: expert system, automated planning, and A* search. / "
            "IA para redes eletricas inteligentes: sistema especialista, planejamento "
            "automatico e busca A*."
        ),
    )
    parser.add_argument("--version", action="version", version=f"aisg {__version__}")
    parser.add_argument(
        "--lang", choices=("pt", "en"), default="pt", help="output language / idioma"
    )
    parser.add_argument(
        "--topology",
        default="dual",
        help=(
            "bundled scenario or path to a JSON file / cenario ou caminho: "
            + ", ".join(sorted(BUNDLED_TOPOLOGIES))
        ),
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # diagnose
    d = sub.add_parser("diagnose", help="run the expert system / executar o sistema especialista")
    d.add_argument("--case", help=f"preset case: {', '.join(SIM_CASES)}")
    d.add_argument(
        "--from-observation", metavar="FILE",
        help="read evidence from an observation record (JSON)",
    )
    d.add_argument(
        "--from-prometheus", metavar="URL",
        help="query a Prometheus instance for the evidence it can answer",
    )
    d.add_argument("--subject", help="link or node id, with --from-prometheus")
    d.add_argument("--specs", metavar="FILE", help="metric spec overrides (JSON)")
    d.add_argument(
        "--save-observation", metavar="FILE",
        help="write the fetched record, so a run can be replayed offline",
    )
    d.add_argument("--interactive", action="store_true", help="ask the user for facts")
    d.add_argument("--mode", choices=("forward", "backward"), default="forward")
    d.add_argument("--goal", default="diagnosis", help="goal variable for backward chaining")
    d.add_argument(
        "--strategy",
        choices=[s.value for s in ConflictResolution],
        default=ConflictResolution.SPECIFICITY.value,
        help="conflict-resolution policy / politica de resolucao de conflito",
    )
    d.add_argument("--trace", action="store_true", help="show the reasoning trace")
    d.add_argument("--explain", action="store_true", help="explain HOW each conclusion was reached")
    d.set_defaults(func=cmd_diagnose)

    # route
    r = sub.add_parser("route", help="A* routing / roteamento por A*")
    r.add_argument("--from", dest="source", help="default: the operations centre")
    r.add_argument("--to", dest="target", help="default: a field device or edge router")
    r.add_argument("--avoid", nargs="*", help="nodes the route must not traverse")
    r.add_argument("--disable-link", nargs="*", metavar="A-B", help="take links out of service")
    r.add_argument("--compare", action="store_true", help="compare BFS, DFS, UCS, greedy, A*")
    r.add_argument("--expansion", action="store_true", help="print the expansion order")
    r.set_defaults(func=cmd_route)

    # plan
    p = sub.add_parser("plan", help="automated planning / planejamento automatico")
    p.add_argument("--diagnosis", default="rf_interference")
    p.add_argument("--node", help="default: a store-and-forward relay")
    p.add_argument("--solver", choices=("gps", "astar", "both"), default="both")
    p.add_argument("--heuristic", choices=("goal_count", "zero"), default="goal_count")
    p.add_argument("--trace", action="store_true", help="show the means-ends trace")
    p.set_defaults(func=cmd_plan)

    # pipeline
    pl = sub.add_parser(
        "pipeline", help="diagnose -> plan -> route / diagnosticar -> planejar -> rotear"
    )
    pl.add_argument("--case", default="congestion", help=f"one of: {', '.join(sorted(SIM_CASES))}")
    pl.add_argument("--node", help="default: a store-and-forward relay")
    pl.add_argument("--target", help="routing destination / destino do roteamento")
    pl.set_defaults(func=cmd_pipeline)

    # blackboard
    bb = sub.add_parser(
        "blackboard", help="multi-expert blackboard / quadro-negro multiespecialista"
    )
    bb.add_argument("--scenario", default="dual-outage",
                    help=f"one of: {', '.join(sorted(SCENARIOS))}")
    bb.add_argument("--list", action="store_true", help="list the scenarios / listar cenarios")
    bb.add_argument("--experts", action="store_true",
                    help="show what each expert reads, writes and knows")
    bb.add_argument("--trace", action="store_true",
                    help="show the incidents, access decisions and plans each cycle posted")
    bb.add_argument("--explain", metavar="NODE",
                    help="every conclusion about one node, with its justification")
    bb.set_defaults(func=cmd_blackboard)

    # ns-3 export
    ns = sub.add_parser(
        "ns3-export", help="export the dual-homed backhaul to ns-3 / exportar o backhaul para o ns-3"
    )
    ns.add_argument("--out", metavar="FILE", help="scenario file to write (default: stdout)")
    ns.add_argument("--sim-time", type=float, help="simulated time, in seconds")
    ns.add_argument("--fault-scenario", choices=sorted(SCENARIOS),
                    help="inject a blackboard scenario's faults and its central failover plan")
    ns.set_defaults(func=cmd_ns3_export)

    # ns-3 telemetry -> diagnosis
    nd = sub.add_parser(
        "ns3-diagnose",
        help="diagnose from simulated telemetry / diagnosticar pela telemetria simulada",
    )
    nd.add_argument("--results", required=True, metavar="DIR",
                    help="run directory holding nodes.csv (simulator flag --probe)")
    nd.add_argument("--fault-scenario", choices=sorted(SCENARIOS),
                    help="score the diagnosis against this scenario's commanded fault")
    nd.add_argument("--save-observations", metavar="DIR",
                    help="write one observation record per node, as JSON")
    nd.add_argument("--unavailable", action="store_true",
                    help="list the evidence the simulator cannot measure, and why")
    nd.set_defaults(func=cmd_ns3_diagnose)

    # eco-resolution
    eco = sub.add_parser("eco", help="eco-resolution / eco-resolucao")
    eco.add_argument("--problem", choices=("blocks", "network"), default="blocks")
    eco.add_argument("--scenario", choices=sorted(SCENARIOS), default="saf-chain-outage",
                     help="network: the blackboard fault scenario")
    eco.add_argument("--sweep", action="store_true",
                     help="blocks: every 3-block initial state against every goal")
    eco.add_argument("--trace", action="store_true", help="network: show the agents' trace")
    eco.set_defaults(func=cmd_eco)

    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except KeyboardInterrupt:
        print("\ninterrupted / interrompido")
        return 130


if __name__ == "__main__":
    sys.exit(main())
