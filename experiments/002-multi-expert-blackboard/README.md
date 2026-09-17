[Applied AI for Wireless Communication](../../README.md) › [experiments](../../docs/experiment-catalogue.md) › **002 Multi-expert blackboard**

# 002 — Quadro-negro multiespecialista / Multi-expert blackboard

> **PT-BR** — Especialistas estreitos, cooperando por um quadro-negro compartilhado sob um controlador central, explicam incidentes de rede que nenhuma base única enxerga — sem alterar nenhuma conclusão sobre um nó isolado.
>
> **EN** — Narrow experts, cooperating through a shared blackboard under a central controller, explain network-wide incidents no single base can see — without changing any conclusion about a single node.

Questão / Question: [RQ4](../../research/research-questions.md) · Código / Code: [`software/aisg/blackboard/`](../../software/aisg/blackboard/) · Testes / Tests: [`test_blackboard.py`](../../software/tests/test_blackboard.py) · Estado / Status: **concluído / complete**

---

## Objetivo / Objective

Estender o diagnóstico de nó único do [experimento 001](../001-symbolic-restoration-chain/) para a rede inteira: fazer especialistas estreitos cooperarem por um quadro-negro compartilhado para explicar incidentes de vários nós, decidir acesso multi-RAT por site e priorizar planos de restauração — sem que a divisão da base em especialistas altere nenhuma conclusão que a base única já produzia sobre um nó isolado.

Extend the [experiment 001](../001-symbolic-restoration-chain/) single-node diagnosis to the whole network: have narrow experts cooperate through a shared blackboard to explain multi-node incidents, decide per-site multi-RAT access, and prioritise restoration plans — without splitting the base into experts changing any conclusion the single base already produced about an isolated node.

## Questão de pesquisa / Research question

> **RQ4 — Cooperação entre especialistas.** Especialistas estreitos sobre um quadro-negro compartilhado explicam incidentes de rede melhor do que uma base única, sem alterar nenhuma conclusão sobre um nó isolado?
>
> **RQ4 — Expert cooperation.** Do narrow experts on a shared blackboard explain network-wide incidents better than a single base, without changing any single-node conclusion?

Ver [`research/research-questions.md`](../../research/research-questions.md) para as demais subquestões (RQ1–RQ6).
See [`research/research-questions.md`](../../research/research-questions.md) for the other sub-questions (RQ1–RQ6).

## Hipótese / Hypothesis

Dividir as 41 regras simuladas do experimento 001 entre sete especialistas de regra não muda nenhuma conclusão de diagnóstico, ação ou autorização em relação à base única, para qualquer caso de nó isolado. Um correlacionador que decide causa comum por profundidade na topologia explica corretamente incidentes com múltiplas interrupções simultâneas, sem nunca fundir falhas genuinamente independentes. O quadro-negro, executado até o ponto fixo, converge — nenhum especialista permanece ativável indefinidamente.

Splitting experiment 001's 41 simulated rules across seven rule experts changes no diagnosis, action or authorisation conclusion versus the single base, for any single-node case. A correlator that decides common cause by topology depth correctly explains incidents with several simultaneous outages, without ever merging genuinely independent faults. The blackboard, run to its fixpoint, converges — no expert stays activatable indefinitely.

Falseabilidade: qualquer divergência de conclusão entre a base única e os especialistas, para os mesmos 8 casos do experimento 001, refuta a hipótese central; uma falha independente fundida a uma causa comum refuta a hipótese do correlacionador.

Falsifiability: any conclusion divergence between the single base and the experts, on experiment 001's same 8 cases, refutes the central hypothesis; an independent fault merged into a common cause refutes the correlator hypothesis.

## Tópicos relacionados / Related topics

- [RQ4](../../research/research-questions.md) — questão respondida por este experimento / the question this experiment answers.
- [Experimento 001](../001-symbolic-restoration-chain/) — os sete especialistas de regra são subconjuntos das mesmas 41 regras, com os mesmos identificadores / the seven rule experts are subsets of the same 41 rules, with the same ids.
- [Experimento 003](../003-eco-resolution/) — usa os incidentes diagnosticados aqui como estado inicial dos agentes de fluxo / uses the incidents diagnosed here as the flow agents' initial state.
- [Experimento 004](../004-multi-rat-simulation/) — verificou por simulação a regra de manutenção do árbitro descrita em [Resultados](#resultados--results) / verified the arbiter's hold rule described in [Results](#resultados--results) by simulation.

## Modelo do sistema / System model

A arquitetura segue o modelo blackboard do Hearsay-II: um quadro com **níveis de abstração**, **fontes de conhecimento** independentes e um **controlador** que decide quem contribui a seguir. Nenhum especialista chama outro.

The architecture follows the Hearsay-II blackboard model: a board with **levels of abstraction**, independent **knowledge sources**, and a **controller** deciding who contributes next. No expert calls another.

| Nível / Level | Conteúdo / Contents |
|---|---|
| L0 | Observações por nó / Per-node observations |
| L1 | Sintomas: qualidade do sinal, sintoma do enlace / Symptoms: signal quality, link symptom |
| L2 | Hipóteses de diagnóstico, ação e autorização / Diagnosis, action and authorisation hypotheses |
| L3 | Incidentes: causas comuns ou locais / Incidents: common or local causes |
| L4 | Acesso multi-RAT: meios perdidos, rotas, decisões / Multi-RAT access: lost media, routes, decisions |
| L5 | Planos de restauração priorizados / Prioritised restoration plans |

| Especialista / Expert | Lê → escreve / Reads → writes | Responsabilidade / Responsibility |
|---|---|---|
| symptom | L0 → L1, L2 | Qualifica sinal e sintoma; reconhece a linha de base (S01–S08, S22) / Grades signal and symptom; recognises the baseline |
| rf | L0, L1 → L2 | Interferência co-canal e perda de percurso (S10–S13, S23, S24) / Co-channel interference and path loss |
| mac | L0, L1 → L2 | Contenção de acesso ao meio (S14, S15, S25) / Medium-access contention |
| availability | L0 → L2 | Nó parado e queda do repetidor a montante (S16–S18, S26) / Stopped node and upstream relay loss |
| routing | L0 → L2 | Nó que responde sem rota (S19) / Responding node with no route |
| traffic | L0, L1 → L2 | Congestionamento (S20, S21) / Congestion |
| action | L2 → L2 | Ação recomendada e janela autorizada (S27–S42) / Recommended action and authorised window |
| correlator | L2 → L3 | Agrupa interrupções simultâneas no nó mais profundo comum às suas rotas / Groups simultaneous outages at the deepest node common to their routes |
| router | L3 → L4 | Meios perdidos por site e rota A\* evitando nós comprometidos e, se possível, degradados / Lost media per site and an A\* route avoiding impaired and, when possible, degraded nodes |
| arbiter | L4 → L4 | Troca de meio, manutenção do meio congestionado quando a alternativa é degradada, redundância perdida ou site isolado / Medium switch, holding a congested medium when the alternative is degraded, lost redundancy or isolated site |
| planner | L3, L4 → L5 | Plano STRIPS por incidente, priorizado por sites isolados, sites afetados, interrupções explicadas e certeza / A STRIPS plan per incident, ranked by isolated sites, affected sites, explained outages and certainty |

Os sete especialistas de regras **não têm regras próprias**: são subconjuntos das 41 regras da base simulada do [experimento 001](../001-symbolic-restoration-chain/), com os mesmos identificadores.
The seven rule experts **have no rules of their own**: they are subsets of the 41 rules of the simulated base from [experiment 001](../001-symbolic-restoration-chain/), with the same ids.

## Cenário e premissas / Scenario and assumptions

Cenário de 60 nós com 15 sites em duplo acesso (LTE privativo + 900 MHz) — a topologia `dual`, a mesma dos experimentos 003 e 004. Ver [`docs/domain-model.md`](../../docs/domain-model.md).

60-node scenario with 15 dual-homed sites (private LTE + 900 MHz) — the `dual` topology, the same one experiments 003 and 004 use. See [`docs/domain-model.md`](../../docs/domain-model.md).

**Premissa de verdade independente.** O cenário decide quem está a jusante por alcançabilidade (BFS) na topologia, não pelas rotas que o próprio correlacionador calcula; os conjuntos esperados de sites isolados são escritos à mão, a partir do grafo, não derivados do sistema sob teste. Verificar o correlacionador com sua própria noção de rota seria circular.

**Independent-ground-truth assumption.** The scenario decides what is downstream by reachability (BFS) on the topology, not by the routes the correlator itself computes; the expected sets of isolated sites are written by hand from the graph, not derived from the system under test. Verifying the correlator with its own notion of route would be circular.

Topologia sintética; resultados valem para o modelo — ver [Limitações](#limitações--limitations).
Synthetic topology; results hold for the model — see [Limitations](#limitações--limitations).

## Software e versões / Software and versions

Mesmo núcleo do experimento 001: Python 3.10+, sem dependências de terceiros; `pytest` como extra de desenvolvimento. Pacote `aisg`, versão 0.11.0.

Same core as experiment 001: Python 3.10+, no third-party dependencies; `pytest` as a development extra. Package `aisg`, version 0.11.0.

## Configuração / Configuration

`CORRELATOR_PARAMETERS` (em [`software/aisg/blackboard/`](../../software/aisg/blackboard/)) são nominais e não otimizados: a decisão de agrupar por parcimônia é uma preferência declarada, não uma prova de que é a única explicação correta. Os limiares de regra são os mesmos `SIM_THRESHOLDS` do experimento 001, compartilhados sem cópia.

`CORRELATOR_PARAMETERS` (in [`software/aisg/blackboard/`](../../software/aisg/blackboard/)) are nominal and unoptimised: grouping by parsimony is a declared preference, not proof it is the only correct explanation. Rule thresholds are experiment 001's same `SIM_THRESHOLDS`, shared without copying.

## Dados de entrada / Input data

Três cenários de falha comandada, cada um também consumido pelos experimentos 003 e 004:

Three commanded-fault scenarios, each also consumed by experiments 003 and 004:

| Cenário / Scenario | Falha comandada / Commanded fault |
|---|---|
| `saf-chain-outage` | SAF_02 parado / stopped |
| `dual-outage` | SAF_02 e / and RELAY_5 parados / stopped |
| `independent-faults` | interferência em RM_07, congestionamento em RELAY_5 / interference at RM_07, congestion at RELAY_5 |

## Procedimento de execução / Execution procedure

```bash
aisg blackboard --list
aisg blackboard --scenario dual-outage --experts --trace --explain ER_03
aisg --lang en blackboard --scenario independent-faults
```

## Métricas / Metrics

- Identidade de conclusão (diagnóstico, ação, autorização, CF) entre base única e especialistas, nos 8 casos do experimento 001 / Conclusion identity (diagnosis, action, authorisation, CF) between the single base and the experts, on experiment 001's 8 cases.
- Conjunto de sites isolados/afetados por incidente, contra o conjunto esperado por alcançabilidade / Set of sites isolated/affected per incident, against the reachability-derived expected set.
- Ciclos até a quiescência / Cycles to quiescence.
- Proveniência: autor e suporte de cada entrada do quadro / Provenance: author and support of every board entry.

## Resultados / Results

| Cenário / Scenario | Falha comandada / Commanded fault | Resultado / Result |
|---|---|---|
| `saf-chain-outage` | SAF_02 parado / stopped | 1 incidente explica 16 interrupções; 12 sites perdem o 900 MHz e seguem em LTE privativo / 1 incident explains 16 outages; 12 sites lose 900 MHz and stay on private LTE |
| `dual-outage` | SAF_02 e / and RELAY_5 | 2 causas separadas; exatamente ER_03, ER_04, ER_06 e ER_07 isolados; SAF_02 priorizado / 2 separate causes; exactly ER_03, ER_04, ER_06 and ER_07 isolated; SAF_02 ranked first |
| `independent-faults` | interferência em RM_07, congestionamento em RELAY_5 / interference at RM_07, congestion at RELAY_5 | nada é fundido; RELAY_5 priorizado por afetar 4 sites; ER_03 e ER_04 trocam para 900 MHz; ER_07 permanece no LTE congestionado, porque sua alternativa atravessa RM_07 degradado / nothing merged; RELAY_5 ranked first for affecting 4 sites; ER_03 and ER_04 switch to 900 MHz; ER_07 holds congested LTE, because its alternative crosses the degraded RM_07 |

A regra de manutenção veio da verificação por simulação no [experimento 004](../004-multi-rat-simulation/): na primeira versão, o quadro-negro trocava ER_07 para o rádio interferido e a perda subia de 14% para 57%. / The hold rule came from simulation-based verification in [experiment 004](../004-multi-rat-simulation/): in the first version, the blackboard moved ER_07 onto the interfered radio and its loss rose from 14% to 57%.

Todos os cenários chegam à quiescência em 11 ciclos. / Every scenario reaches quiescence in 11 cycles.

| Propriedade / Property | Como / How |
|---|---|
| Dividir a base não muda conclusões / Splitting the base changes no conclusion | Nos 8 casos, diagnóstico, ação e autorização idênticos à base única, com o mesmo CF / Across 8 cases, diagnosis, action and authorisation identical to the single base, same CF |
| Toda regra pertence a exatamente um especialista / Every rule belongs to exactly one expert | Partição verificada / Partition checked |
| Verdade independente / Independent ground truth | O cenário decide quem está a jusante por alcançabilidade (BFS), não pelas rotas do correlacionador; conjuntos esperados escritos à mão / The scenario decides what is downstream by reachability (BFS), not the correlator's routes; expected sets written by hand |
| Falhas independentes não se fundem / Independent faults never merge | Testado / Tested |
| Quiescência e ponto fixo / Quiescence and fixpoint | Uma segunda execução não ativa nenhum especialista / A second pass activates no expert |
| Proveniência / Provenance | Toda entrada tem autor conhecido e suporte; especialistas de regras citam só as próprias regras / Every entry has a known author and support; rule experts cite only their own rules |

## Limitações / Limitations

- Parâmetros do correlacionador (`CORRELATOR_PARAMETERS`) são nominais: parcimônia é preferência, não prova. / Correlator parameters are nominal: parsimony is a preference, not a proof.
- Uma falha real a montante somada a uma falha local coincidente pode ser atribuída inteiramente à causa comum. / A real upstream failure coinciding with an unrelated local failure may be attributed entirely to the common cause.
- A política de prioridade é declarada, não otimizada. / The priority policy is declared, not optimised.
- Topologia sintética; resultados valem para o modelo. / Synthetic topology; results hold for the model.

## Estado de reprodutibilidade / Reproducibility status

**Reproduzível.** Os três cenários são falhas comandadas, deterministicamente diagnosticadas; `test_blackboard.py` cobre identidade de conclusão, correlação e quiescência, e roda no mesmo workflow de CI dos demais experimentos. Nenhuma medição de laboratório está envolvida.

**Reproducible.** The three scenarios are commanded faults, deterministically diagnosed; `test_blackboard.py` covers conclusion identity, correlation and quiescence, and runs in the same CI workflow as the other experiments. No laboratory measurement is involved.

## Material de manuscrito relacionado / Related manuscript material

`manuscripts/presentations/` — deck, roteiro de fala e notebook: locais, não publicados neste repositório; a wiki é a companhia pública. / deck, speaking script and notebook: local, not published in this repository; the wiki is the public companion.
