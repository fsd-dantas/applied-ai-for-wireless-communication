"""
Network-wide experts: what no single-subject rule base can see.

PT-BR: Os especialistas de regras raciocinam sobre UM no de cada vez. Os quatro
       especialistas deste modulo raciocinam sobre a REDE:

       * o correlacionador junta varias interrupcoes numa causa comum;
       * o roteador de acesso descobre quais sites perderam um meio e recalcula a
         rota por A*, evitando os nos comprometidos;
       * o arbitro multi-RAT decide, site a site, entre trocar de meio, apenas
         registrar perda de redundancia, ou declarar o site isolado;
       * o planejador transforma cada incidente num plano STRIPS e ordena os planos
         pelo dano que cada causa provoca.

EN:    The rule experts reason about ONE node at a time. The four experts in this
       module reason about the NETWORK:

       * the correlator gathers several outages into one common cause;
       * the access router finds which sites lost a medium and recomputes the route
         with A*, avoiding the impaired nodes;
       * the multi-RAT arbiter decides, site by site, between switching medium,
         merely recording lost redundancy, or declaring the site isolated;
       * the planner turns each incident into a STRIPS plan and orders the plans by
         the damage each cause does.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Set, Tuple

from aisg.blackboard.board import Blackboard, Entry, Level
from aisg.blackboard.sources import KnowledgeSource
from aisg.domain.diagnoses import DIAGNOSES, RoutingEffect
from aisg.domain.topology import Topology
from aisg.expert_system import FIRING_THRESHOLD, combine_cf
from aisg.planning import plan_with_astar, problem_from_diagnosis
from aisg.search import RoutingProblem, astar, shortest_route

#: NOMINAL, UNCALIBRATED. Declared in one block, like the rule thresholds.
CORRELATOR_PARAMETERS: Dict[str, float] = {
    # How much a common upstream cause is believed when every outage it explains
    # is fully certain. Below 1 because parsimony is a preference, not a proof.
    "rule_cf": 0.85,
    # Fewer simultaneous outages than this are not worth a common cause.
    "min_cluster": 2,
}

#: Diagnoses that mean "this node cannot carry traffic".
OUTAGE_DIAGNOSES = tuple(
    name for name, contract in DIAGNOSES.items() if contract.correlates_as_outage
)

#: Exclude impaired nodes; prefer routes avoiding degraded nodes where possible.
IMPAIRING_DIAGNOSES = tuple(
    name for name, contract in DIAGNOSES.items()
    if contract.routing_effect == RoutingEffect.EXCLUDE
)
DEGRADING_DIAGNOSES = tuple(
    name for name, contract in DIAGNOSES.items()
    if contract.routing_effect == RoutingEffect.AVOID_IF_POSSIBLE
)

#: Radio access technologies, by the node kind that terminates them at a site.
ACCESS_MEDIUM: Dict[str, str] = {"cpe": "plte", "remote_radio": "radio900"}

MEDIUM_LABELS: Dict[str, Tuple[str, str]] = {
    "plte": ("LTE privativo", "private LTE"),
    "radio900": ("radio 900 MHz", "900 MHz radio"),
    "wired": ("rede cabeada", "wired network"),
}


def medium_label(medium: str, lang: str = "pt") -> str:
    pt, en = MEDIUM_LABELS.get(medium, (medium, medium))
    return pt if lang == "pt" else en


def control_centre(topology: Topology) -> str:
    for node in topology.nodes.values():
        if node.kind == "control_centre":
            return node.id
    return next(iter(topology.nodes))


def path_medium(topology: Topology, path: List[str]) -> str:
    """The radio medium a route uses to reach the site, or ``wired``."""
    types = set()
    for u, v in zip(path, path[1:]):
        link = min(
            (lk for nb, lk in topology.neighbours(u) if nb == v),
            key=topology.link_cost,
        )
        types.add(link.type)
    if "lte" in types:
        return "plte"
    if types & {"radio_900mhz", "radio_900mhz_saf"}:
        return "radio900"
    return "wired"


class _RouteCache:
    """Nominal routes from the control centre, computed once per topology."""

    def __init__(self, topology: Topology) -> None:
        self.topology = topology
        self.source = control_centre(topology)
        self._routes: Dict[str, Optional[List[str]]] = {}

    def to(self, node: str) -> Optional[List[str]]:
        if node not in self._routes:
            self._routes[node] = (
                [self.source] if node == self.source
                else shortest_route(self.topology, self.source, node)
            )
        return self._routes[node]

    def depth(self, node: str) -> int:
        route = self.to(node)
        return len(route) - 1 if route else 0


# ---------------------------------------------------------------------------
class IncidentCorrelator(KnowledgeSource):
    """
    Explain simultaneous outages by the deepest node common to their routes.

    PT-BR: Heuristica de parcimonia: N interrupcoes simultaneas cujas rotas passam
           todas pelo mesmo no tem uma explicacao mais simples do que N falhas
           independentes. O escolhido e o no que cobre mais interrupcoes; no empate,
           o mais profundo, isto e, o mais proximo das interrupcoes. Um no observado
           como saudavel nunca e culpado. O processo repete-se sobre o que sobrou,
           o que separa duas causas simultaneas.
    EN:    A parsimony heuristic: N simultaneous outages whose routes all cross the
           same node have a simpler explanation than N independent failures. The
           chosen node covers the most outages; on a tie, the deepest one, closest to
           the outages. A node observed healthy is never blamed. The process repeats
           on what is left, which separates two simultaneous causes.
    """

    name = "correlator"
    label_pt, label_en = "Correlacionador de incidentes", "Incident correlator"
    expertise_pt = "Agrupa interrupcoes simultaneas numa causa comum a montante."
    expertise_en = "Groups simultaneous outages into one common upstream cause."
    reads = (Level.HYPOTHESIS,)
    writes = (Level.INCIDENT,)
    priority = 40

    def __init__(self, topology: Topology) -> None:
        super().__init__()
        self.topology = topology
        self.routes = _RouteCache(topology)

    def _contribute(self, board: Blackboard) -> Tuple[int, int]:
        best: Dict[str, Tuple[str, float]] = {}
        for subject in board.subjects(Level.HYPOTHESIS):
            ranked = board.ranked(
                Level.HYPOTHESIS, subject, "diagnosis", min_cf=FIRING_THRESHOLD
            )
            if ranked:
                best[subject] = (str(ranked[0][0]), ranked[0][1])

        outages = {s: hc for s, hc in best.items() if hc[0] in OUTAGE_DIAGNOSES}
        healthy = {s for s, (value, _cf) in best.items() if value == "healthy"}
        remaining = {s for s in outages if self.routes.to(s)}
        explained: Set[str] = set()
        new: List[Entry] = []

        while remaining:
            coverage: Dict[str, Set[str]] = {}
            for subject in remaining:
                for node in self.routes.to(subject) or ():
                    if node == self.routes.source or node in healthy:
                        continue
                    if self.topology.node(node).stub:
                        continue
                    coverage.setdefault(node, set()).add(subject)
            if not coverage:
                break
            root = min(
                coverage,
                key=lambda n: (-len(coverage[n]), -self.routes.depth(n), n),
            )
            covered = coverage[root]
            if len(covered) < CORRELATOR_PARAMETERS["min_cluster"]:
                break

            explains = sorted(covered - {root})
            premise = min(outages[s][1] for s in explains)
            cf = premise * CORRELATOR_PARAMETERS["rule_cf"]
            if root in outages:
                cf = combine_cf(cf, outages[root][1])
            observed = root in best
            new.append(Entry(
                level=Level.INCIDENT,
                subject=root,
                key="incident",
                value="node_failure",
                cf=cf,
                author=self.name,
                support=tuple(f"{s}:{outages[s][0]}" for s in explains),
                data={
                    "kind": "correlated",
                    "explains": explains,
                    "observed": observed,
                    "depth": self.routes.depth(root),
                },
                rationale_pt=(
                    f"{len(explains)} interrupcoes simultaneas tem rotas que passam por "
                    f"{root}; uma causa comum e mais simples do que {len(explains)} falhas "
                    f"independentes. Premissa {premise:+.2f} (a interrupcao menos certa) "
                    f"x regra {CORRELATOR_PARAMETERS['rule_cf']:+.2f}"
                    + (f", combinada com a observacao do proprio {root}." if root in outages
                       else f"; {root} nao foi observado, a falha e INFERIDA.")
                ),
                rationale_en=(
                    f"{len(explains)} simultaneous outages have routes crossing {root}; "
                    f"one common cause is simpler than {len(explains)} independent "
                    f"failures. Premise {premise:+.2f} (the least certain outage) x rule "
                    f"{CORRELATOR_PARAMETERS['rule_cf']:+.2f}"
                    + (f", combined with {root}'s own observation." if root in outages
                       else f"; {root} was not observed, so the failure is INFERRED.")
                ),
            ))
            explained |= covered
            remaining -= covered

        for subject, (value, cf) in sorted(best.items()):
            if subject in explained or value == "healthy":
                continue
            new.append(Entry(
                level=Level.INCIDENT,
                subject=subject,
                key="incident",
                value=value,
                cf=cf,
                author=self.name,
                support=(f"{subject}:{value}",),
                data={"kind": "local", "explains": [], "observed": True,
                      "depth": self.routes.depth(subject)},
                rationale_pt="Hipotese local, sem outra interrupcao que a explique.",
                rationale_en="A local hypothesis, with no other outage to explain it.",
            ))
        return board.publish(self.name, new, levels=self.writes)


# ---------------------------------------------------------------------------
class AccessRouter(KnowledgeSource):
    """
    For every grid site, find which access media the incidents cut, and reroute.

    PT-BR: Um meio de acesso esta PERDIDO quando a rota nominal ate o no que o
           termina no site (CPE para LTE, radio remoto para 900 MHz) passa por um
           no comprometido. A nova rota ate o site e calculada por A* evitando
           todos os nos comprometidos. Se ela atravessar um no DEGRADADO, tenta-se
           uma rota que tambem o evite; nao havendo, a rota fica, sinalizada.
    EN:    An access medium is LOST when the nominal route to the node terminating
           it at the site (CPE for LTE, remote radio for 900 MHz) crosses an
           impaired node. The new route to the site is computed by A* avoiding every
           impaired node. If it crosses a DEGRADED node, a route avoiding that node
           too is tried; if none exists, the route stays, flagged.
    """

    name = "router"
    label_pt, label_en = "Roteador de acesso (A*)", "Access router (A*)"
    expertise_pt = "Meios de acesso perdidos por site e a rota A* que evita os nos comprometidos."
    expertise_en = "Access media lost per site, and the A* route avoiding impaired nodes."
    reads = (Level.INCIDENT,)
    writes = (Level.ACCESS,)
    priority = 50

    def __init__(self, topology: Topology) -> None:
        super().__init__()
        self.topology = topology
        self.routes = _RouteCache(topology)

    def _route(self, site: str, avoid: Tuple[str, ...]):
        problem = RoutingProblem(self.topology, self.routes.source, site, avoid)
        return astar(problem, problem.heuristic())

    def _contribute(self, board: Blackboard) -> Tuple[int, int]:
        incidents = board.entries(Level.INCIDENT, key="incident")
        impaired = sorted({
            e.subject for e in incidents
            if e.value in IMPAIRING_DIAGNOSES and e.cf > FIRING_THRESHOLD
        })
        degraded = sorted({
            e.subject for e in incidents
            if e.value in DEGRADING_DIAGNOSES and e.cf > FIRING_THRESHOLD
        })
        diagnosis_by_node = {
            e.subject: str(e.value) for e in incidents if e.subject in set(impaired)
        }
        impaired_set = set(impaired)
        new: List[Entry] = []
        sites = sorted(n.id for n in self.topology.nodes.values() if n.stub)

        for site in sites:
            media_down: Dict[str, List[str]] = {}
            for access, _link in self.topology.neighbours(site):
                medium = ACCESS_MEDIUM.get(self.topology.node(access).kind)
                route = self.routes.to(access)
                if medium is None or route is None:
                    continue
                blockers = sorted(set(route) & impaired_set)
                if blockers:
                    media_down[medium] = blockers
            if not media_down:
                continue

            nominal = self.routes.to(site) or []
            avoid = tuple(n for n in impaired if n not in (self.routes.source, site))
            result = self._route(site, avoid)
            crosses = sorted(set(result.path) & set(degraded)) if result.found else []
            if crosses:
                cleaner = self._route(site, avoid + tuple(
                    n for n in degraded if n not in avoid and n not in (self.routes.source, site)
                ))
                if cleaner.found:
                    result, crosses = cleaner, []
            blockers = sorted({b for bl in media_down.values() for b in bl})
            new.append(Entry(
                level=Level.ACCESS,
                subject=site,
                key="route",
                value="restored" if result.found else "unreachable",
                cf=1.0,
                author=self.name,
                support=tuple(blockers),
                data={
                    "media_down": media_down,
                    "nominal_path": nominal,
                    "nominal_medium": path_medium(self.topology, nominal) if nominal else None,
                    "path": list(result.path),
                    "medium": path_medium(self.topology, result.path) if result.found else None,
                    "cost_ms": round(result.cost, 3) if result.found else None,
                    "expanded": result.expanded,
                    "avoid": list(avoid),
                    "crosses_degraded": crosses,
                    "blocker_diagnoses": {b: diagnosis_by_node.get(b, "") for b in blockers},
                },
                rationale_pt=(
                    "Rota calculada por A* com heuristica de linha reta (admissivel), "
                    f"evitando {', '.join(avoid) or 'nenhum no'}."
                    + (f" Nao ha rota que evite tambem {', '.join(crosses)}, degradado(s)."
                       if crosses else "")
                ),
                rationale_en=(
                    "Route computed by A* with the straight-line (admissible) heuristic, "
                    f"avoiding {', '.join(avoid) or 'no node'}."
                    + (f" No route also avoids {', '.join(crosses)}, which is degraded."
                       if crosses else "")
                ),
            ))
        return board.publish(self.name, new, levels=self.writes)


# ---------------------------------------------------------------------------
class MultiRatArbiter(KnowledgeSource):
    """
    Decide, per site, what the loss of an access medium means.

    PT-BR: Quatro regras de politica, na ordem em que sao testadas:
           1. sem rota restante                           -> site ISOLADO (so o reparo resolve);
           2. o meio NOMINAL so esta congestionado e a
              alternativa passa por no degradado          -> MANTER o meio nominal;
           3. o meio NOMINAL foi perdido                  -> TROCAR de meio;
           4. so o meio de reserva caiu                   -> REDUNDANCIA PERDIDA (nada muda agora).
           A regra 2 veio da simulacao: trocar congestionamento por um radio
           interferido elevou a perda de ER_07 de 14% para 57%.
    EN:    Four policy rules, in the order they are tested:
           1. no route left                               -> site ISOLATED (only repair helps);
           2. the NOMINAL medium is only congested and
              the alternative crosses a degraded node     -> HOLD the nominal medium;
           3. the NOMINAL medium was lost                 -> SWITCH medium;
           4. only the backup medium fell                 -> REDUNDANCY LOST (nothing changes now).
           Rule 2 came from simulation: trading congestion for an interfered
           radio raised ER_07's loss from 14% to 57%.
    """

    name = "arbiter"
    label_pt, label_en = "Arbitro multi-RAT", "Multi-RAT arbiter"
    expertise_pt = "Decide troca de meio, perda de redundancia ou isolamento de cada site."
    expertise_en = "Decides medium switch, lost redundancy, or isolation for each site."
    reads = (Level.ACCESS,)
    writes = (Level.ACCESS,)
    priority = 60

    def _contribute(self, board: Blackboard) -> Tuple[int, int]:
        new: List[Entry] = []
        for route in sorted(
            board.entries(Level.ACCESS, key="route", author="router"),
            key=lambda e: e.subject,
        ):
            data = route.data
            lost = sorted(data["media_down"])
            blockers = sorted({b for bl in data["media_down"].values() for b in bl})
            nominal = data["nominal_medium"]
            if route.value == "unreachable":
                decision, detail = "isolated", {}
                pt = (f"Nenhuma rota restante: {', '.join(medium_label(m, 'pt') for m in lost)} "
                      f"perdidos. So o reparo de {', '.join(blockers)} restaura o site.")
                en = (f"No route left: {', '.join(medium_label(m, 'en') for m in lost)} "
                      f"lost. Only repairing {', '.join(blockers)} restores the site.")
            elif (
                nominal in data["media_down"]
                and data.get("crosses_degraded")
                and all(
                    data.get("blocker_diagnoses", {}).get(b) == "congestion"
                    for b in data["media_down"][nominal]
                )
            ):
                decision = "hold"
                detail = {"stay_on": nominal, "degraded_via": data["crosses_degraded"]}
                via = ", ".join(data["crosses_degraded"])
                pt = (f"O meio nominal ({medium_label(nominal, 'pt')}) esta congestionado, mas "
                      f"a alternativa passa por {via}, ja degradado: o site permanece no meio "
                      f"nominal.")
                en = (f"The nominal medium ({medium_label(nominal, 'en')}) is congested, but the "
                      f"alternative crosses {via}, already degraded: the site stays on the "
                      f"nominal medium.")
            elif nominal in data["media_down"]:
                decision = "switch_medium"
                detail = {"from": nominal, "to": data["medium"]}
                pt = (f"O meio nominal ({medium_label(nominal, 'pt')}) caiu; o trafego passa "
                      f"para {medium_label(data['medium'], 'pt')}.")
                en = (f"The nominal medium ({medium_label(nominal, 'en')}) is down; traffic "
                      f"moves to {medium_label(data['medium'], 'en')}.")
            else:
                decision = "redundancy_lost"
                detail = {"lost": lost, "serving": data["medium"]}
                pt = (f"So o meio de reserva caiu; o site segue em "
                      f"{medium_label(data['medium'], 'pt')}, sem redundancia.")
                en = (f"Only the backup medium is down; the site stays on "
                      f"{medium_label(data['medium'], 'en')}, without redundancy.")
            if data.get("crosses_degraded") and decision != "hold":
                via = ", ".join(data["crosses_degraded"])
                detail = {**detail, "degraded_via": data["crosses_degraded"]}
                pt += f" A rota passa por {via}, ja degradado: servico com qualidade reduzida."
                en += f" The route crosses {via}, already degraded: service at reduced quality."
            new.append(Entry(
                level=Level.ACCESS,
                subject=route.subject,
                key="decision",
                value=decision,
                cf=1.0,
                author=self.name,
                support=tuple(blockers),
                data={"blockers": blockers, **detail},
                rationale_pt=pt,
                rationale_en=en,
            ))
        return board.publish(self.name, new, levels=self.writes)


# ---------------------------------------------------------------------------
class RestorationPlanner(KnowledgeSource):
    """
    One STRIPS plan per incident, ranked by the damage its cause does.

    PT-BR: Ordem de prioridade: primeiro a causa que isola mais sites; depois a que
           afeta mais sites; depois a que explica mais interrupcoes; depois a de
           maior certeza. A ordem e uma politica declarada, e nao uma otimizacao.
    EN:    Priority order: first the cause isolating the most sites; then the one
           affecting the most sites; then the one explaining the most outages; then
           the most certain. The order is a declared policy, not an optimisation.
    """

    name = "planner"
    label_pt, label_en = "Planejador de restauracao (STRIPS)", "Restoration planner (STRIPS)"
    expertise_pt = "Plano de reparo por incidente, com prioridade pelo dano causado."
    expertise_en = "A repair plan per incident, prioritised by the damage caused."
    reads = (Level.INCIDENT, Level.ACCESS)
    writes = (Level.PLAN,)
    priority = 70

    def __init__(self, topology: Topology) -> None:
        super().__init__()
        self.topology = topology

    def _contribute(self, board: Blackboard) -> Tuple[int, int]:
        decisions = board.entries(Level.ACCESS, key="decision", author="arbiter")
        routes = board.entries(Level.ACCESS, key="route", author="router")
        drafts = []
        for incident in board.entries(Level.INCIDENT, key="incident"):
            if incident.cf <= FIRING_THRESHOLD:
                continue
            root, diagnosis = incident.subject, str(incident.value)
            target = None
            if diagnosis == "congestion":
                target = next(
                    (r.subject for r in sorted(routes, key=lambda e: e.subject)
                     if root in r.support),
                    None,
                )
            problem = problem_from_diagnosis(
                diagnosis, root, topology=self.topology, reroute_target=target
            )
            plan, search = plan_with_astar(problem)
            valid, reason = plan.validate() if plan is not None else (False, "no plan found")
            affected = sorted(d.subject for d in decisions if root in d.support)
            isolated = sorted(
                d.subject for d in decisions if d.value == "isolated" and root in d.support
            )
            drafts.append((incident, plan, search, valid, reason, isolated, affected))

        drafts.sort(key=lambda d: (
            -len(d[5]), -len(d[6]), -len(d[0].data.get("explains", [])), -d[0].cf,
            d[0].subject,
        ))
        new: List[Entry] = []
        for rank, draft in enumerate(drafts, start=1):
            incident, plan, search, valid, reason, isolated, affected = draft
            actions = [str(a) for a in plan.actions] if plan is not None else []
            explains = incident.data.get("explains", [])
            new.append(Entry(
                level=Level.PLAN,
                subject=incident.subject,
                key="plan",
                value="found" if plan is not None else "none",
                cf=incident.cf,
                author=self.name,
                support=(f"incident:{incident.subject}:{incident.value}",),
                data={
                    "priority": rank,
                    "diagnosis": incident.value,
                    "actions": actions,
                    "cost": plan.cost if plan is not None else None,
                    "valid": valid,
                    "invalid_reason": reason,
                    "expanded": search.expanded,
                    "isolated_sites": isolated,
                    "affected_sites": affected,
                    "explains": explains,
                },
                rationale_pt=(
                    f"Prioridade {rank}: isola {len(isolated)} site(s), afeta "
                    f"{len(affected)}, explica {len(explains)} interrupcao(oes), "
                    f"CF {incident.cf:+.2f}."
                ),
                rationale_en=(
                    f"Priority {rank}: isolates {len(isolated)} site(s), affects "
                    f"{len(affected)}, explains {len(explains)} outage(s), "
                    f"CF {incident.cf:+.2f}."
                ),
            ))
        return board.publish(self.name, new, levels=self.writes)
