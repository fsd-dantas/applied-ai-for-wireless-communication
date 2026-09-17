# Ontologia do domínio / Domain ontology

## Propósito / Purpose

Esta ontologia define, em lógica de descrição, as classes e relações compartilhadas pelos quatro experimentos. A arquitetura ([`architecture.md`](../docs/architecture.md)) descreve **processos** — o que acontece, em que camada, em que ordem; esta ontologia descreve os **conceitos** sobre os quais esses processos operam — o que é um `Node`, um `Diagnosis`, um `Incident`, um `Plan`, um `Agent`, e como se relacionam. Sem ela, cada experimento reinventa parte do vocabulário do anterior (002 introduz `Incident` sem declarar sua relação com `Diagnosis`; 003 introduz `Agent` sem declarar sua relação com `KnowledgeSource`; 004 introduz `SiteResult` sem declarar contra o que ele é avaliado).

This ontology defines, in description logic, the classes and relations shared by the four experiments. The architecture ([`architecture.md`](../docs/architecture.md)) describes **processes** — what happens, in which layer, in what order; this ontology describes the **concepts** those processes operate on — what a `Node`, a `Diagnosis`, an `Incident`, a `Plan`, an `Agent` is, and how they relate. Without it, each experiment quietly reinvents part of the previous one's vocabulary (002 introduces `Incident` without stating its relation to `Diagnosis`; 003 introduces `Agent` without stating its relation to `KnowledgeSource`; 004 introduces `SiteResult` without stating what it is scored against).

**Estado / Status.** Apresentação híbrida: notação DL abaixo para a semântica, sintaxe Manchester junto de cada axioma central, e a ontologia OWL 2 completa e executável em [`ontology.ttl`](ontology.ttl) — validada por um raciocinador real, ver [Validação](#validação--validation).
**Hybrid presentation: DL notation below for the semantics, Manchester syntax alongside each key axiom, and the complete, executable OWL 2 ontology in [`ontology.ttl`](ontology.ttl)** — checked by a real reasoner, see [Validation](#validação--validation).

## Convenções / Conventions

| Símbolo / Symbol | Significado / Meaning |
|---|---|
| `⊑` | é subclasse de / rdfs:subClassOf |
| `≡` | é equivalente a (definição) / is equivalent to (definition) |
| `⊓` | e / conjunction |
| `⊔` | ou / disjunction |
| `¬` | não / negation |
| `∃r.C` | existe pelo menos um `r` para `C` / owl:someValuesFrom |
| `∀r.C` | todo `r` é `C` / owl:allValuesFrom |
| `⊤` / `⊥` | tudo / nada (topo, disjunção vazia) / thing / nothing (top, disjointness) |
| `≤n r`, `=n r` | restrição de cardinalidade / cardinality restriction |

Prefixo / namespace: `:` (ex. `:Node`, `:hasCost`). Correspondência a OWL: `⊑` → `SubClassOf`, `≡` → `EquivalentClasses`, `C ⊓ D ⊑ ⊥` → `DisjointClasses`.
Prefix / namespace: `:` (e.g. `:Node`, `:hasCost`). Mapping to OWL: `⊑` → `SubClassOf`, `≡` → `EquivalentClasses`, `C ⊓ D ⊑ ⊥` → `DisjointClasses`.

## Hierarquia de classes / Class hierarchy

| Camada / Layer | Classes |
|---|---|
| Domínio compartilhado / Shared domain | `NetworkElement`, `Node` (7 subclasses), `Link` (5 subclasses), `Medium`, `Site`, `Topology` |
| 1 — Raciocínio / Reasoning (001) | `Observation`, `Conclusion` (`Symptom`, `Diagnosis`, `RecommendedAction`, `AuthorizationRequirement`), `CertaintyFactor`, `Rule`, `Predicate`, `Action`, `Plan`, `Goal`, `Route` |
| 2 — Coordenação / Coordination (002, 003) | `Actor` (`KnowledgeSource`, `Agent` — disjuntas / disjoint), `BlackboardLevel`, `Incident`, `Place`, `Behaviour`, `FlowAgent` |
| 3 — Verificação / Verification (004) | `Scenario`, `Fault`, `Simulation`, `SiteResult` |

## TBox — Domínio compartilhado / Shared domain

```
NetworkElement ⊑ ⊤
Node ⊑ NetworkElement
ControlCentre, LteEnb, LteRelay, SafRelay, EdgeRouter, Cpe, RemoteRadio ⊑ Node
ControlCentre ⊓ LteEnb ⊓ LteRelay ⊓ SafRelay ⊓ EdgeRouter ⊓ Cpe ⊓ RemoteRadio ⊑ ⊥   (pairwise disjoint)

Link ⊑ NetworkElement
FibreLink, EthernetLink, LteLink, Radio900Link, Radio900SafLink ⊑ Link   (pairwise disjoint)
Link ⊑ =1 connects⁻¹ ⊓ =1 connects        (connects exactly two Nodes — see RBox)
Link ⊑ =1 hasQuality ⊓ =1 hasCostFunction

Medium ⊑ ⊤ ;  Medium ≡ {PrivateLte, Radio900}        (enumerated, 2 individuals)

Site ≡ ∃hasComponent.EdgeRouter ⊓ ∃hasComponent.Cpe ⊓ ∃hasComponent.RemoteRadio
EdgeRouter ⊑ ¬∃carries.Traffic                        ("stub": a route may start/end
                                                         here but never cross it)

Topology ⊑ ⊤ ;  Topology ⊑ ∃hasNode.Node ⊓ ∃hasLink.Link
```

Os sete tipos de `Node` e os cinco de `Link` são exatamente os valores de `kind`/`type` declarados em [`backhaul-topology-60.json`](../software/aisg/domain/data/backhaul-topology-60.json), verificado neste repositório.
The seven `Node` and five `Link` types are exactly the `kind`/`type` values declared in [`backhaul-topology-60.json`](../software/aisg/domain/data/backhaul-topology-60.json), verified against this repository.

## TBox — Camada 1: Raciocínio / Layer 1: Reasoning (001)

```
Observation ⊑ ⊤ ;  Observation ⊑ =1 hasValue ⊓ =1 observedAt.Node

Conclusion ⊑ ⊤ ;  Conclusion ⊑ =1 hasCertaintyFactor.CertaintyFactor
Symptom, Diagnosis, RecommendedAction, AuthorizationRequirement ⊑ Conclusion   (pairwise disjoint)
CertaintyFactor ⊑ ⊤ ;  CertaintyFactor ⊑ =1 hasNumericValue   (range [-1, +1])

Congestion, ExcessPathLoss, Healthy, MacContention, NodeFailure, RfInterference,
RoutingMisconfiguration, UpstreamRelayFailure ⊑ Diagnosis   (8 disjoint subclasses,
                                                              e.g. :diag_ER06 a :NodeFailure)

Rule ⊑ ⊤ ;  Rule ⊑ =1 belongsToLayer ⊓ ∃hasPremise.Predicate ⊓ ∃concludes.Conclusion
          ⊓ =1 hasRuleCertaintyFactor

Predicate ⊑ ⊤                                          (a named, bound literal, STRIPS-style)

Action ⊑ ⊤ ;  Action ⊑ ∃hasPrecondition.Predicate ⊓ ∃hasAddList.Predicate
            ⊓ ∀hasDeleteList.Predicate ⊓ =1 hasCost
Action ⊑ ∃proposedBy.RecommendedAction                 (every Action a plan can use
                                                          traces to a layer-4 conclusion)

Plan ⊑ ⊤ ;  Plan ⊑ ∃consistsOf.Action ⊓ =1 achieves.Goal ⊓ ∃derivedFrom.Diagnosis
Goal ⊑ ⊤ ;  Goal ⊑ ∃requires.Predicate

Route ⊑ ⊤ ;  Route ⊑ ∃consistsOf.Link ⊓ =1 hasOrigin.Node ⊓ =1 hasDestination.Node
           ⊓ =1 hasRouteCost
```

## TBox — Camada 2: Coordenação / Layer 2: Coordination (002, 003)

Este é o núcleo formal que separa quadro-negro de sistema multiagente / this is the formal core that separates blackboard from multi-agent system:

```
Actor ⊑ ⊤                                              (abstract parent)
KnowledgeSource ⊑ Actor
Agent ⊑ Actor
KnowledgeSource ⊓ Agent ⊑ ⊥                             (DISJOINT — an Actor is one or the
                                                          other, never both)

KnowledgeSource ⊑ ∃scheduledBy.Controller ⊓ ¬∃calls.KnowledgeSource
                ⊓ ∃reads.BlackboardLevel ⊓ ∃writes.BlackboardLevel
RuleKnowledgeSource ⊑ KnowledgeSource ⊓ ∃builtFrom.Rule       (7 of 11: symptom, rf, mac,
                                                                availability, routing, traffic, action)
CorrelatorKS, RouterKS, ArbiterKS, PlannerKS ⊑ KnowledgeSource  (the other 4, independently
                                                                  defined, pairwise disjoint)

Agent ⊑ ¬∃scheduledBy.Controller                        (autonomy — the exact negation
                                                          of KnowledgeSource's defining trait)
Agent ⊑ =1 hasGoal.Goal ⊓ =1 occupies.Place ⊓ ∃performs.Behaviour
Behaviour ≡ {Satisfaction, Aggression, Flight, Dependency}    (enumerated, 4)
FlowAgent ⊑ Agent ⊓ =1 hasPriority ⊓ =1 representsTraffic     ({SCADA, Telemetry})
Place ≡ ∃occupiesMedium.Medium ⊓ ∃atSite.Site                 (network variant of Place)

BlackboardLevel ≡ {L0, L1, L2, L3, L4, L5}              (enumerated, strictly ordered)

Incident ⊑ ⊤ ;  Incident ⊑ ∃correlates.Diagnosis ⊓ =1 hasCommonCause.Node
```

## TBox — Camada 3: Verificação / Layer 3: Verification (004)

```
Scenario ⊑ ⊤ ;  Scenario ⊑ =1 overTopology.Topology ⊓ ∀commandsFault.Fault

Fault ⊑ ⊤ ;  Fault ⊑ =1 occursAt.Node ⊓ =1 occursAtTime
Fault ⊑ ¬∃readBy.Actor                                  (EPISTEMIC BOUNDARY: no
                                                          KnowledgeSource or Agent may
                                                          read a Fault — it exists only
                                                          to score the outcome)

Simulation ⊑ ⊤ ;  Simulation ⊑ =1 executes.Scenario ⊓ ∃produces.SiteResult
SiteResult ⊑ ⊤ ;  SiteResult ⊑ =1 hasLossPercent ⊓ =1 hasRttMean
                 ⊓ ∃scoredAgainst.(Diagnosis ⊔ Incident ⊔ Plan)
```

## RBox — Propriedades / Properties

| Propriedade / Property | Domínio / Domain | Alcance / Range | Características / Characteristics |
|---|---|---|---|
| `connects` | `Link` | `Node` | exatamente 2 por Link / exactly 2 per Link |
| `hasComponent` | `Site` | `Node` | — |
| `observedAt` | `Observation` | `Node` | funcional / functional |
| `concludes` | `Rule` | `Conclusion` | — |
| `hasPremise` | `Rule` | `Predicate` | — |
| `derivedFrom` | `Plan` | `Diagnosis` | funcional / functional |
| `consistsOf` | `Plan`, `Route` | `Action`, `Link` | ordenado (não capturado em OWL puro) / ordered (not captured in plain OWL) |
| `builtFrom` | `RuleKnowledgeSource` | `Rule` | um-para-muitos / one-to-many |
| `reads`, `writes` | `KnowledgeSource` | `BlackboardLevel` | — |
| `scheduledBy` | `KnowledgeSource` | `Controller` | funcional / functional |
| `occupies` | `Agent` | `Place` | funcional / functional |
| `correlates` | `Incident` | `Diagnosis` | mín. 1 / min 1 |
| `commandsFault` | `Scenario` | `Fault` | — |
| `readBy` | `Fault` | `Actor` | **vazio por axioma** / **empty by axiom** |
| `scoredAgainst` | `SiteResult` | `Diagnosis`, `Incident`, `Plan` | — |

## Axiomas centrais, comentados / Key axioms, annotated

**1. `Site ≡ ∃hasComponent.EdgeRouter ⊓ ∃hasComponent.Cpe ⊓ ∃hasComponent.RemoteRadio`**
Um `Site` não é um tipo de nó — é **definido** por ter as três componentes. Isso é uma classe de definição (`≡`), não só uma subclasse (`⊑`): qualquer coisa com essas três componentes É um site, por construção.
A `Site` is not a node type — it is **defined** by having the three components. This is a definitional class (`≡`), not merely a subclass (`⊑`): anything with those three components IS a site, by construction.

```manchester
Class: Site
    EquivalentTo:
        (hasComponent some EdgeRouter)
        and (hasComponent some Cpe)
        and (hasComponent some RemoteRadio)
```

**2. `EdgeRouter ⊑ ¬∃carries.Traffic`**
Formaliza a regra "stub" já declarada em prosa no [modelo de domínio](../docs/domain-model.md): uma rota pode começar ou terminar num `EdgeRouter`, nunca atravessá-lo.
Formalises the "stub" rule already stated in prose in the [domain model](../docs/domain-model.md): a route may begin or end at an `EdgeRouter`, never cross it.

```manchester
Class: EdgeRouter
    SubClassOf:
        not (carries some Traffic)
```

**3. `KnowledgeSource ⊓ Agent ⊑ ⊥` e `Agent ⊑ ¬∃scheduledBy.Controller`**
A distinção entre 002 e 003 não é de nomenclatura — é uma classe disjunta com uma propriedade que é a negação exata da outra. Isso é o que torna "central vs. reativo" uma comparação válida: os dois métodos resolvem a mesma tarefa (alocação de meio) sob modelos computacionais estruturalmente diferentes, não apenas rotulados diferente.
The distinction between 002 and 003 is not naming — it is a disjoint class pair where one's defining property is the exact negation of the other's. This is what makes "central vs. reactive" a valid comparison: the two methods solve the same task (medium allocation) under structurally different computational models, not merely differently labelled ones.

```manchester
Class: KnowledgeSource
    SubClassOf: Actor
    DisjointWith: Agent

Class: Agent
    SubClassOf: Actor
    SubClassOf: not (scheduledBy some Controller)
```

**4. `Fault ⊑ ¬∃readBy.Actor`**
Formaliza o compromisso já declarado em [`methodology.md`](methodology.md) ("a verdade comandada serve só para avaliar"): nenhum `KnowledgeSource` nem `Agent` — nenhum `Actor` — pode ler um `Fault`. A fronteira epistêmica entre "o que o sistema decide" e "o que realmente aconteceu" vira uma restrição de classe, não apenas uma convenção de código.
Formalises the commitment already stated in [`methodology.md`](methodology.md) ("commanded ground truth is for scoring only"): no `KnowledgeSource` and no `Agent` — no `Actor` — may read a `Fault`. The epistemic boundary between "what the system decides" and "what actually happened" becomes a class restriction, not merely a coding convention.

```manchester
Class: Fault
    SubClassOf:
        not (readBy some Actor)
```

**5. `Action ⊑ ∃proposedBy.RecommendedAction`**
Toda ação que um `Plan` pode usar remonta a uma conclusão da camada 4 do sistema especialista — nenhuma ação "aparece" no planejador sem uma recomendação rastreável. É a mesma exigência de auditabilidade da questão de pesquisa central, expressa como axioma.
Every action a `Plan` can use traces back to a layer-4 expert-system conclusion — no action "appears" in the planner without a traceable recommendation. This is the central research question's auditability requirement, expressed as an axiom.

## Exemplo instanciado (ABox) / Worked example

O exemplo instanciado **não é mais escrito à mão** — é gerado por [`export_abox.py`](export_abox.py), que executa de verdade o quadro-negro (002) e a eco-resolução (003) sobre o cenário `saf-chain-outage`, e lê os resultados reais e já commitados do ns-3 (004, `failover=central`). Saída: [`scenario-abox.ttl`](scenario-abox.ttl) — arquivo gerado, não editar à mão; regenerar com `PYTHONPATH=software python research/export_abox.py`.

The worked example is **no longer hand-typed** — it is generated by [`export_abox.py`](export_abox.py), which actually runs the blackboard (002) and eco-resolution (003) over the `saf-chain-outage` scenario, and reads the real, already-committed ns-3 results (004, `failover=central`). Output: [`scenario-abox.ttl`](scenario-abox.ttl) — generated file, do not hand-edit; regenerate with `PYTHONPATH=software python research/export_abox.py`.

Nenhum número abaixo foi inventado; cada um vem de um objeto vivo ou de um arquivo de resultado já commitado / no number below was invented; each comes from a live object or an already-committed results file:

| Indivíduo / Individual | Vem de / Comes from |
|---|---|
| `:diag_SAF_02 a :NodeFailure` (cf 0.8) | regra real `S16` disparada pelo motor / rule `S16` really fired by the engine |
| `:incident_SAF_02` (cf 0.96575, correlaciona 16 nós / correlates 16 nodes) | correlacionador real do quadro-negro / the blackboard's real correlator |
| `:plan_SAF_02` (5 ações, custo 5.0 / 5 actions, cost 5.0) | planejador real, ações e custos de `build_operators()` / real planner, action costs from `build_operators()` |
| `:agent_ER_06_telemetry` (satisfied=False) | eco-resolução real: `ER_06/telemetry` e `ER_07/telemetry` insatisfeitas / real eco-resolution: `ER_06/telemetry` and `ER_07/telemetry` unsatisfied |
| `:fault_SAF_02` (t=10s), `:result_ER_06` (perda 14.29% / 14.29% loss) | `events.csv`/`sites.csv` reais do experimento 004 / experiment 004's real `events.csv`/`sites.csv` |

`:fault_SAF_02` não aparece em nenhum triplo de `:diag_SAF_02`, `:incident_SAF_02`, `:plan_SAF_02`, `:ks_router` ou `:ks_arbiter` — exatamente o que o Axioma 4 exige, verificado no dado real, não só declarado. Só `:result_ER_06`, da camada de verificação, referencia o diagnóstico e o plano para pontuá-los.

`:fault_SAF_02` appears in no triple of `:diag_SAF_02`, `:incident_SAF_02`, `:plan_SAF_02`, `:ks_router` or `:ks_arbiter` — exactly what Axiom 4 requires, verified on real data, not just declared. Only `:result_ER_06`, from the verification layer, references the diagnosis and plan in order to score them.

**Duas perdas, duas definições / Two losses, two definitions.** O `:hasLossPercent` deste ABox vem de `sites.csv` e vale **14,29%**: ER_06 envia 14 consultas SCADA e recebe 12. A tabela de Resultados do [experimento 004](../experiments/004-multi-rat-simulation/README.md) diz **0%**, e as duas estão corretas — são métricas diferentes. O README mede a janela de 16–29 s, onde cabem sete consultas; `sites.csv` mede a execução inteira. As duas consultas perdidas saem em t=10,222 s e t=12,222 s, ou seja, entre a falha (t=10 s) e a troca de meio (t=13 s), e portanto antes da janela abrir. Dentro da janela, as sete consultas são respondidas.

O ABox registra deliberadamente a figura da execução inteira, que é o que o simulador grava. Cuidado ao comparar as duas: 2/14 e 1/7 dão o mesmo percentual, então "14,29%" sozinho não diz qual definição está em uso.

`:hasLossPercent` in this ABox comes from `sites.csv` and reads **14.29%**: ER_06 sends 14 SCADA polls and receives 12. [Experiment 004](../experiments/004-multi-rat-simulation/README.md)'s Results table says **0%**, and both are right — they are different metrics. The README measures the 16–29 s window, which holds seven polls; `sites.csv` measures the whole run. The two lost polls leave at t=10.222 s and t=12.222 s, between the fault (t=10 s) and the medium switch (t=13 s), and so before the window opens. Inside the window all seven are answered.

The ABox deliberately records the whole-run figure, which is what the simulator writes. Compare the two with care: 2/14 and 1/7 are the same percentage, so "14.29%" alone does not say which definition is in play.

## Validação / Validation

Dois artefatos, verificados separadamente e juntos / two artefacts, checked separately and together:

| Verificação / Check | Ferramenta / Tool | Resultado / Result |
|---|---|---|
| Sintaxe Turtle válida / Valid Turtle syntax | `rdflib` | `ontology.ttl` (470 triplas/triples) e `scenario-abox.ttl` juntos: 539 triplas sem erro / together: 539 triples parsed with no error |
| Consistência lógica, só TBox/RBox / Logical consistency, TBox/RBox only | `owlready2` + raciocinador **HermiT** (real, via Java) / `owlready2` + the **HermiT** reasoner (real, via Java) | 59 classes, **zero insatisfazíveis** / 59 classes, **zero unsatisfiable** |
| Consistência lógica, TBox+RBox+ABox real / Logical consistency, TBox+RBox+real ABox | idem, com `scenario-abox.ttl` carregado / same, with `scenario-abox.ttl` loaded | **33 indivíduos, consistente, zero insatisfazíveis** (19 do ABox + 14 declarados no próprio TBox) / **33 individuals, consistent, zero unsatisfiable** (19 from the ABox + 14 declared in the TBox itself) |

**Achado do raciocinador, não escrito à mão.** O HermiT deduziu, por conta própria, que `:calls` e `:readBy` são **propriedades permanentemente vazias** (equivalentes a `owl:bottomObjectProperty`): nenhuma instância de nenhuma das duas pode existir sem contradizer a ontologia. Isso não é um erro — é exatamente o que os Axiomas 3 e 4 pretendiam, agora confirmado por máquina em vez de apenas afirmado em prosa: um `KnowledgeSource` nunca pode chamar outro `KnowledgeSource`, e um `Fault` nunca pode ser lido por um `Actor`.

**Reasoner finding, not hand-written.** HermiT deduced on its own that `:calls` and `:readBy` are **permanently empty properties** (equivalent to `owl:bottomObjectProperty`): no instance of either can exist without contradicting the ontology. That is not a bug — it is exactly what Axioms 3 and 4 intended, now machine-confirmed rather than merely asserted in prose: a `KnowledgeSource` can never call another `KnowledgeSource`, and a `Fault` can never be read by an `Actor`.

**Como contar os indivíduos, e duas contagens anteriores erradas.** `owlready2.Ontology.individuals()` devolve **0** aqui, e isso é um falso negativo conhecido: ele não encontra indivíduos declarados só por `a ClassName` em Turtle, sem a tipagem explícita `owl:NamedIndividual` — que nenhum dos dois arquivos usa. A contagem reproduzível é por SPARQL sobre o grafo combinado, contando sujeitos IRI com um `rdf:type` que não seja de esquema:

```sparql
SELECT (COUNT(DISTINCT ?s) AS ?n) WHERE {
  ?s a ?t . FILTER(isIRI(?s) && isIRI(?t))
  FILTER(?t != owl:Class && ?t != owl:ObjectProperty && ?t != owl:DatatypeProperty
         && ?t != owl:FunctionalProperty && ?t != owl:Ontology
         && ?t != owl:AllDisjointClasses && ?t != owl:Restriction)
}
```

Resultado: **33** — 19 do `scenario-abox.ttl` gerado e 14 declarados no próprio `ontology.ttl` (`:PrivateLte`, `:Radio900`, `:L0`–`:L5`, os quatro `:Behaviour`, `:Scada`, `:Telemetry`). Uma versão anterior desta seção relatava "0 indivíduos"; outra relatava 102. O 102 **não se reproduz** por nenhum método tentado (SPARQL, `Class.instances()`, sujeitos tipados, IRIs do namespace) e provavelmente vem de quando o exemplo instanciado ainda era escrito à mão dentro de `ontology.ttl`, antes de `export_abox.py` existir. Registrado aqui em vez de apagado, para não esconder nenhuma das duas contagens erradas.

**How to count the individuals, and two earlier miscounts.** `owlready2.Ontology.individuals()` returns **0** here, which is a known false negative: it does not find individuals declared with plain `a ClassName` in Turtle without explicit `owl:NamedIndividual` typing, which neither file uses. The reproducible count is a SPARQL query over the merged graph, counting IRI subjects with a non-schema `rdf:type` (query above). Result: **33** — 19 from the generated `scenario-abox.ttl` and 14 declared in `ontology.ttl` itself. An earlier version of this section reported "0 individuals"; another reported 102. The 102 **does not reproduce** under any method tried (SPARQL, `Class.instances()`, typed subjects, namespace IRIs) and most likely dates from when the worked example was still hand-written inside `ontology.ttl`, before `export_abox.py` existed. Recorded here rather than deleted, so neither miscount is hidden.

## Correspondência com o código / Mapping to the code

| Classe / Class | Onde no código / Where in the code |
|---|---|
| `Node`, `Link`, `Site`, `Topology` | [`software/aisg/domain/data/backhaul-topology-60.json`](../software/aisg/domain/data/backhaul-topology-60.json) |
| `Observation`…`AuthorizationRequirement`, `Rule` | [`software/aisg/expert_system/kb_simulated.py`](../software/aisg/expert_system/kb_simulated.py) — 41 rules, ids `S01`–`S42` |
| `Action`, `Plan`, `Goal` | [`software/aisg/planning/domain_restoration.py`](../software/aisg/planning/domain_restoration.py) — 13 operators, verified against the running code 2026-09-15 |
| `Route` | [`software/aisg/search/algorithms.py`](../software/aisg/search/algorithms.py) |
| `KnowledgeSource`, `BlackboardLevel`, `Incident` | [`software/aisg/blackboard/`](../software/aisg/blackboard/) |
| `Agent`, `Place`, `Behaviour`, `FlowAgent` | [`software/aisg/eco/`](../software/aisg/eco/) |
| `Scenario`, `Fault`, `Simulation`, `SiteResult` | [`software/ns-3-modules/dual-homed-backhaul/`](../software/ns-3-modules/dual-homed-backhaul/), [`software/aisg/simulation/`](../software/aisg/simulation/) |

## Limitações / Limitations

- **O ABox cobre um cenário, não o domínio inteiro.** `scenario-abox.ttl` é gerado de uma execução real, mas de **uma** execução: `saf-chain-outage`, com foco em `SAF_02` e no site `ER_06`. Os outros dois cenários de falha, os outros catorze sites e os diagnósticos que esse cenário não produz não têm indivíduos. A ontologia está verificada como consistente com esse recorte, e não exercitada contra todos os casos que o TBox admite.
  **The ABox covers one scenario, not the whole domain.** `scenario-abox.ttl` is generated from a real run, but from **one** run: `saf-chain-outage`, centred on `SAF_02` and the site `ER_06`. The other two fault scenarios, the other fourteen sites, and the diagnoses that scenario never produces have no individuals. The ontology is verified consistent with that slice, not exercised against every case the TBox admits.
- **Ordem não é capturada.** `Plan.consistsOf` e `Route.consistsOf` são, na implementação, sequências; OWL padrão só expressa conjuntos. Uma extensão futura precisaria de listas RDF ou uma ontologia de processo (ex. OWL-S).
  **Ordering is not captured.** `Plan.consistsOf` and `Route.consistsOf` are sequences in the implementation; plain OWL only expresses sets. A future extension would need RDF lists or a process ontology (e.g. OWL-S).
- **Sem lógica temporal.** `occursAtTime` é um valor de dado simples; comparar `Fault` e troca de meio por instante (como o experimento 004 faz em prosa) exigiria uma extensão temporal (ex. Allen's interval algebra), não incluída aqui.
  **No temporal logic.** `occursAtTime` is a plain data value; comparing `Fault` and medium-switch timing (as experiment 004 does in prose) would need a temporal extension (e.g. Allen's interval algebra), not included here.
- **Os 13 operadores vieram do código, não da prosa — e isso valeu a pena.** Quando este mapeamento foi escrito, `planning.md` ainda listava doze operadores, sete deles inexistentes (`dispatch_crew`, `monitor_and_wait` e outros). Verificar contra o código em execução manteve a ontologia correta enquanto o documento estava errado; `planning.md` foi corrigido em 2026-09-17 e agora traz os mesmos 13 operadores registrados aqui.
  **The 13 operators came from the code, not from prose — and that paid off.** When this mapping was written, `planning.md` still listed twelve operators, seven of which did not exist (`dispatch_crew`, `monitor_and_wait` and others). Verifying against the running code kept the ontology right while the document was wrong; `planning.md` was corrected on 2026-09-17 and now carries the same 13 operators recorded here.
