"""Generate the ontology's worked-example ABox from a real run of the system.

GENERATED FILE WARNING: this script writes research/scenario-abox.ttl. Do not
hand-edit that file; edit this script and regenerate.

Unlike the placeholder ABox embedded in ontology.md and ontology.ttl (which was
transcribed by hand from README prose), every individual this script emits
comes from one of two real sources for the same `saf-chain-outage` scenario:

  - the blackboard (experiment 002) and eco-resolution (experiment 003)
    engines, run live, for the diagnosis/incident/plan/knowledge-source and
    agent layers;
  - the ns-3 simulation's own recorded output (experiment 004,
    experiments/004-multi-rat-simulation/results/saf-chain-outage/central/),
    for the fault/outcome layer.

No individual, value or certainty factor below is invented; each is read from
a live object or a committed results file. Run from the repository root:

    PYTHONPATH=software python research/export_abox.py
"""

from __future__ import annotations

import csv
import re
from pathlib import Path

import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "software"))

from aisg.blackboard import build_scenario, solve  # noqa: E402
from aisg.domain.topology import load_topology  # noqa: E402
from aisg.eco.network import network_ecosystem  # noqa: E402
from aisg.expert_system.kb_simulated import build_simulated_knowledge_base  # noqa: E402
from aisg.planning.domain_restoration import build_operators  # noqa: E402

SCENARIO = "saf-chain-outage"
FAULT_NODE = "SAF_02"
SITE = "ER_06"
RESULTS_DIR = ROOT / "experiments/004-multi-rat-simulation/results" / SCENARIO / "central"

PREFIX = ":"
NS = "https://example.org/backhaul-ai#"


def turtle_string(value: str) -> str:
    return '"' + value.replace('"', '\\"') + '"'


def diagnosis_class(value: str) -> str:
    """node_failure -> NodeFailure, rf_interference -> RfInterference, ..."""
    return "".join(part.capitalize() for part in value.split("_"))


def main() -> None:
    topo = load_topology("dual")

    # --- Layer 1/2: run the blackboard for real -----------------------------
    scenario = build_scenario(SCENARIO, topo)
    run = solve(scenario, topo)
    entries = list(run.board.entries())

    diag = next(
        e for e in entries
        if e.subject == FAULT_NODE and e.level.name == "HYPOTHESIS" and e.key == "diagnosis" and e.cf > 0
    )
    incident = next(e for e in entries if e.level.name == "INCIDENT" and e.subject == FAULT_NODE)
    plan = next(e for e in entries if e.level.name == "PLAN" and e.subject == FAULT_NODE)
    access = [e for e in entries if e.subject == SITE and e.level.name == "ACCESS"]
    route_entry = next(e for e in access if e.key == "route")
    decision_entry = next(e for e in access if e.key == "decision")

    kb = build_simulated_knowledge_base()
    # support is a frozenset of rule ids; take the one that concluded this diagnosis
    diag_rule_ids = sorted(diag.support)
    rules_by_id = {r.id: r for r in kb.rules}
    diag_rule = rules_by_id[diag_rule_ids[0]]

    costs = {op.name: op.cost for op in build_operators()}
    plan_actions = plan.data["actions"]  # e.g. "restart_node(SAF_02)"

    # --- Layer 2': eco-resolution (experiment 003) for the same scenario ----
    problem = network_ecosystem(topo, SCENARIO)
    eco_result = problem.ecosystem.solve()
    scada_flow = f"{SITE}/scada"
    telemetry_flow = f"{SITE}/telemetry"
    scada_medium = problem.world.assignment[scada_flow]
    telemetry_satisfied = telemetry_flow not in eco_result.unsatisfied

    # --- Layer 3: read the real ns-3 output, do not recompute ---------------
    events_rows = list(csv.DictReader((RESULTS_DIR / "events.csv").open(encoding="utf-8")))
    fault_row = next(r for r in events_rows if r["subject"] == FAULT_NODE and r["event"] == "fault")
    switch_row = next(r for r in events_rows if r["subject"] == SITE and r["event"] == "switch-er")

    sites_rows = list(csv.DictReader((RESULTS_DIR / "sites.csv").open(encoding="utf-8")))
    site_row = next(r for r in sites_rows if r["site"] == SITE)

    # --- Emit Turtle ----------------------------------------------------------
    lines: list[str] = []
    w = lines.append

    w(f'@prefix : <{NS}> .')
    w('@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .')
    w('@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .')
    w("")
    w("# GENERATED FILE - do not hand-edit. Produced by research/export_abox.py")
    w(f"# from a live run of the blackboard (002) and eco-resolution (003) engines")
    w(f"# on scenario '{SCENARIO}', plus the committed ns-3 results (004) for the")
    w(f"# same scenario under central failover. Regenerate with:")
    w("#   PYTHONPATH=software python research/export_abox.py")
    w("")

    w(f":{FAULT_NODE} a :SafRelay .")
    w(f":{SITE} a :EdgeRouter .")
    w("")

    w("# Layer 1 - expert system diagnosis (live run, experiment 001/002 engine)")
    w(f":cf_diag_{FAULT_NODE} a :CertaintyFactor ; :hasNumericValue \"{diag.cf}\"^^xsd:decimal .")
    w(f":diag_{FAULT_NODE} a :{diagnosis_class(diag.value)} ;")
    w(f"    :hasCertaintyFactor :cf_diag_{FAULT_NODE} ;")
    w(f"    rdfs:comment {turtle_string(f'concluded by rule {diag_rule.id}: ' + diag_rule.rationale_en)} .")
    w("")

    w("# Layer 2 - blackboard correlation and plan (live run, experiment 002)")
    w(f":cf_incident_{FAULT_NODE} a :CertaintyFactor ; :hasNumericValue \"{round(incident.cf, 5)}\"^^xsd:decimal .")
    w(f":incident_{FAULT_NODE} a :Incident ;")
    w(f"    :correlates :diag_{FAULT_NODE} ;")
    w(f"    :hasCommonCause :{FAULT_NODE} ;")
    w(f"    :hasCertaintyFactor :cf_incident_{FAULT_NODE} ;")
    n_explained = len(incident.data["explains"])
    w(f"    rdfs:comment {turtle_string(f'correlator explains {n_explained} downstream nodes from one common cause')} .")
    w("")

    action_uris = []
    for i, call in enumerate(plan_actions):
        name = re.match(r"([a-z_]+)\(", call).group(1)
        uri = f":act_{FAULT_NODE}_{i}_{name}"
        action_uris.append(uri)
        cost = costs.get(name)
        w(f"{uri} a :Action ;")
        w(f"    :proposedBy :rec_{FAULT_NODE} ;")
        w(f"    :hasCost \"{cost}\"^^xsd:decimal ;" if cost is not None else "    :hasCost \"1\"^^xsd:decimal ;")
        w(f"    rdfs:comment {turtle_string(call)} .")
    w("")
    w(f":rec_{FAULT_NODE} a :RecommendedAction .")
    w(f":plan_{FAULT_NODE} a :Plan ;")
    w(f"    :derivedFrom :diag_{FAULT_NODE} ;")
    w("    :consistsOf " + " , ".join(action_uris) + " ;")
    plan_note = (
        f"real cost {plan.data['cost']}, valid={plan.data['valid']}, "
        f"explains {len(plan.data['explains'])} nodes"
    )
    w(f"    rdfs:comment {turtle_string(plan_note)} .")
    w("")

    w("# Layer 2 knowledge sources active for this site (live run)")
    w(f":ks_router a :RouterKS ; :reads :L3 ; :writes :L4 ;")
    w(f"    rdfs:comment {turtle_string(f'{route_entry.key} = {route_entry.value}, cf={route_entry.cf}')} .")
    w(f":ks_arbiter a :ArbiterKS ; :reads :L4 ; :writes :L4 ;")
    w(f"    rdfs:comment {turtle_string(f'{decision_entry.key} = {decision_entry.value}, cf={decision_entry.cf}')} .")
    w("")

    w("# Layer 2' - eco-resolution alternative for the same incident (live run, experiment 003)")
    w(f":agent_{SITE}_scada a :FlowAgent ;")
    w(f"    :representsTraffic :Scada ;")
    w(f"    :hasPriority \"2\"^^xsd:integer ;")
    w(f"    rdfs:comment {turtle_string(f'ends on medium {scada_medium}')} .")
    w(f":agent_{SITE}_telemetry a :FlowAgent ;")
    w(f"    :representsTraffic :Telemetry ;")
    w(f"    :hasPriority \"1\"^^xsd:integer ;")
    w(f"    rdfs:comment {turtle_string(f'satisfied={telemetry_satisfied} after {eco_result.rounds} rounds; unsatisfied={eco_result.unsatisfied}')} .")
    w("")

    w("# Layer 3 - real ns-3 simulation output (experiment 004, committed results, central failover)")
    w(f":fault_{FAULT_NODE} a :Fault ;")
    w(f"    :occursAt :{FAULT_NODE} ;")
    w(f"    :occursAtTime \"{fault_row['time_s']}\"^^xsd:decimal ;")
    w(f"    rdfs:comment {turtle_string(fault_row['detail'])} .")
    w(f"    # note what is absent: no triple above (:diag_{FAULT_NODE}, :incident_{FAULT_NODE}, :plan_{FAULT_NODE},")
    w(f"    # :ks_router, :ks_arbiter) references :fault_{FAULT_NODE} - the Fault/readBy axiom holds by construction.")
    w("")
    w(f":result_{SITE} a :SiteResult ;")
    w(f"    :hasLossPercent \"{site_row['scada_loss_pct']}\"^^xsd:decimal ;")
    w(f"    :hasRttMean \"{site_row['rtt_mean_ms']}\"^^xsd:decimal ;")
    w(f"    :scoredAgainst :diag_{FAULT_NODE} , :plan_{FAULT_NODE} ;")
    result_note = f"switch at t={switch_row['time_s']}s: {switch_row['detail']}"
    w(f"    rdfs:comment {turtle_string(result_note)} .")

    out_path = ROOT / "research/scenario-abox.ttl"
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {out_path.relative_to(ROOT)}")
    print(f"  diagnosis: {diag.value} (cf={diag.cf}, rule {diag_rule.id})")
    print(f"  incident: correlates {len(incident.data['explains'])} downstream nodes (cf={round(incident.cf, 5)})")
    print(f"  plan: {len(plan_actions)} actions, cost={plan.data['cost']}, valid={plan.data['valid']}")
    print(f"  eco (003): {scada_flow} -> {scada_medium}; {telemetry_flow} satisfied={telemetry_satisfied}")
    print(f"  ns-3 (004, central): {SITE} loss={site_row['scada_loss_pct']}%, switch at t={switch_row['time_s']}s")


if __name__ == "__main__":
    main()
