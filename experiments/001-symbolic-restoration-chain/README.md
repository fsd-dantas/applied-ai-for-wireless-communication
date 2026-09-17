
[Applied AI for Wireless Communication](../../README.md) › [experiments](../../docs/experiment-catalogue.md) › **001 Symbolic restoration chain**

# 001 — Symbolic AI for Network Restoration

[![tests](https://github.com/fsd-dantas/applied-ai-for-wireless-communication/actions/workflows/tests.yml/badge.svg)](https://github.com/fsd-dantas/applied-ai-for-wireless-communication/actions/workflows/tests.yml)
[![license: MIT](https://img.shields.io/badge/license-MIT-555555)](../../LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-3776ab)](../../pyproject.toml)

> **PT-BR** — Três sistemas simbólicos de Inteligência Artificial aplicados a um mesmo domínio: redes de comunicação sem fio para sistemas elétricos inteligentes. Um sistema especialista de diagnóstico, um gerador automático de planos de ação (STRIPS / GPS) e uma implementação de busca A*.
>
> **EN** — Three symbolic Artificial Intelligence systems applied to a single domain: wireless networks for smart grid systems. A diagnostic expert system, an automated action-plan generator (STRIPS / GPS), and an A* search implementation.

Questão / Question: [RQ1–RQ3](../../research/research-questions.md) · Estado / Status: **concluído / complete**

---

## Objetivo / Objective

Construir e conectar três sistemas simbólicos de IA — um sistema especialista de diagnóstico, um planejador STRIPS/GPS e uma busca A* — sobre um único domínio de rede, de modo que o diagnóstico de um incidente produza automaticamente o estado inicial de um plano ordenado de intervenção, e que uma ação de desvio de tráfego só seja aplicável quando a busca A* confirma que existe rota alternativa. Nenhum dos três sistemas é demonstrado isoladamente: o objetivo é a cadeia, não as partes.

Build and connect three symbolic AI systems — a diagnostic expert system, a STRIPS/GPS planner and an A* search — over a single network domain, so that diagnosing an incident automatically becomes a plan's initial state, and a reroute-traffic action is applicable only when A* search confirms an alternative route exists. None of the three systems is demonstrated in isolation: the chain is the point, not the parts.

## Questão de pesquisa / Research question

> Na ausência de um conjunto de dados rotulado de falhas, é possível construir um
> encadeamento **diagnóstico → plano → rota** que seja simultaneamente *auditável*
> — cada conclusão rastreável até a evidência que a sustenta — e *verificável*,
> isto é, cujas propriedades de correção sejam asseguradas por testes e não
> apenas afirmadas em prosa?
>
> In the absence of a labelled fault dataset, can a **diagnosis → plan → route**
> chain be built that is both *auditable* — every conclusion traceable to the
> evidence supporting it — and *verifiable*, meaning its correctness properties
> are asserted by tests rather than merely claimed in prose?

A pergunta é metodológica antes de ser técnica. Ela nasce de uma restrição real do laboratório, e não de uma preferência estética por métodos simbólicos: a condição de contorno é a **indisponibilidade de rótulo derivado de medição**, e a resposta precisa ser honesta quanto ao que essa restrição permite concluir.

The question is methodological before it is technical. It arises from a real laboratory constraint rather than an aesthetic preference for symbolic methods: the boundary condition is the **unavailability of measurement-derived labels**, and the answer has to be honest about what that constraint permits concluding.

Três subquestões organizam os três sistemas / three sub-questions organise the three systems:

1. **Representação do conhecimento / Knowledge representation.** Como codificar julgamento de engenharia sob incerteza de modo que a cadeia de inferência permaneça inspecionável e contestável? *(regras de produção com fatores de certeza)* / How can engineering judgement under uncertainty be encoded so the inference chain stays inspectable and contestable? *(production rules with certainty factors)*
2. **Deliberação / Deliberation.** Como derivar a **ordem** de intervenção — e não apenas o conjunto de ações — expressando restrições como precondições formais, e não como verificações em tempo de execução? *(STRIPS, GPS, planejamento progressivo)* / How is the **order** of intervention derived — not merely the set of actions — expressing constraints as formal preconditions rather than as runtime checks? *(STRIPS, GPS, progression planning)*
3. **Otimalidade demonstrável / Demonstrable optimality.** Sob que condições uma busca informada garante o caminho de menor custo, e como *demonstrar* que a heurística adotada satisfaz essas condições neste domínio? *(A\*, admissibilidade, consistência)* / Under what conditions does an informed search guarantee the least-cost path, and how is the chosen heuristic *shown* to meet them in this domain? *(A\*, admissibility, consistency)*

## Hipótese / Hypothesis

Um encadeamento **diagnóstico → plano → rota** construído inteiramente com métodos simbólicos — regras de produção com fatores de certeza, STRIPS/GPS e A\* — pode ser auditável e verificável sem qualquer conjunto de dados rotulado de falha, desde que cada propriedade de correção seja testada contra um oráculo que não compartilhe código com o artefato. Três hipóteses específicas, testáveis independentemente, decorrem disso: (i) a heurística em linha reta do A\* é admissível e consistente neste domínio, para todo par de nós; (ii) todo plano gerado pelo GPS ou pela busca progressiva é executável desde o estado inicial e nunca declara sucesso sobre uma falha viva; (iii) a busca informada (A\*) expande menos nós que a busca de custo uniforme sobre o mesmo grafo, para o mesmo par origem-destino.

A **diagnosis → plan → route** chain built entirely from symbolic methods — production rules with certainty factors, STRIPS/GPS and A\* — can be auditable and verifiable without any labelled fault dataset, provided every correctness property is tested against an oracle sharing no code with the artefact. Three specific, independently testable hypotheses follow: (i) A\*'s straight-line heuristic is admissible and consistent in this domain, for every node pair; (ii) every plan produced by GPS or progression search is executable from the initial state and never declares success over a live fault; (iii) informed search (A\*) expands fewer nodes than uniform-cost search over the same graph, for the same origin–destination pair.

Falseabilidade declarada: se (i) falhar para qualquer par, a otimalidade do A\* deixa de estar demonstrada neste domínio; se (ii) falhar para qualquer plano, o planejador não é confiável; (iii) é uma hipótese de eficiência, não de correção, e sua falha não invalida (i) nem (ii) — ver [Limitações](#limitações--limitations).

Declared falsifiability: if (i) fails for any pair, A\*'s optimality is no longer demonstrated in this domain; if (ii) fails for any plan, the planner is not trustworthy; (iii) is an efficiency hypothesis, not a correctness one, and its failure invalidates neither (i) nor (ii) — see [Limitations](#limitações--limitations).

## Tópicos relacionados / Related topics

- [RQ1–RQ3](../../research/research-questions.md) — questões de pesquisa que este experimento responde / the research questions this experiment answers.
- [Experimento 002](../002-multi-expert-blackboard/) — os especialistas de regra são subconjuntos das mesmas 41 regras simuladas deste experimento, com os mesmos identificadores / the rule experts are subsets of this experiment's same 41 simulated rules, with the same ids.
- [Experimento 003](../003-eco-resolution/) e [004](../004-multi-rat-simulation/) — reutilizam o mesmo domínio de rede (topologia `dual`, 60 nós) declarado aqui / reuse the same network domain (the `dual` 60-node topology) declared here.
- [`literature/systematic-review/al-ajlan-2015/`](../../literature/systematic-review/al-ajlan-2015/) — mede encadeamento progressivo × regressivo sobre esta mesma base de 41 regras / measures forward vs backward chaining over this same 41-rule base.
- Referências completas em [Referências](#referências--references) abaixo / full references in [References](#referências--references) below.

## Modelo do sistema / System model

| # | Sistema / System | Técnica / Technique | Código / Code |
|---|---|---|---|
| 1 | Sistema especialista / Expert system | Regras de produção, encadeamento progressivo e regressivo, fatores de certeza / Production rules, forward and backward chaining, certainty factors | [`expert_system/`](../../software/aisg/expert_system/) |
| 2 | Geração de planos / Plan generation | STRIPS + GPS (análise meios-fins) + planejamento progressivo por A* / STRIPS + GPS (means-ends analysis) + A* progression planning | [`planning/`](../../software/aisg/planning/) |
| 3 | Busca A* / A* search | A*, custo uniforme, gulosa, largura, profundidade / A*, uniform cost, greedy, breadth-first, depth-first | [`search/`](../../software/aisg/search/) |

**Os três se conectam.** O diagnóstico produzido pelo sistema especialista vira o estado inicial do planejador; a ação *desviar tráfego* só é aplicável quando a busca A* confirma que existe rota alternativa; e o planejador progressivo usa **a mesma função A***, sem cópia, que resolve o roteamento.

**The three connect.** The expert system's diagnosis becomes the planner's initial state; the *reroute traffic* action is applicable only when A* search confirms an alternative route exists; and the progression planner uses **the same A\* function**, not a copy, that solves routing.

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/fsd-dantas/applied-ai-for-wireless-communication/main/docs/assets/figures/01-integration-dark.svg">
    <img src="https://raw.githubusercontent.com/fsd-dantas/applied-ai-for-wireless-communication/main/docs/assets/figures/01-integration-light.svg" alt="The expert system produces a diagnosis that becomes the planner's initial state; the planner asks A* whether an alternative route exists; and the progression planner reuses the same A* function that solves routing." width="100%">
  </picture>
</p>

| Diagrama / Diagram | Conteúdo / Contents |
|---|---|
| [Integration](../../docs/assets/figures/01-integration-light.svg) · [dark](../../docs/assets/figures/01-integration-dark.svg) | How the three systems exchange information |
| [Expert system](../../docs/assets/figures/02-expert-system-light.svg) · [dark](../../docs/assets/figures/02-expert-system-dark.svg) | The five rule layers and both chaining directions |
| [Planning](../../docs/assets/figures/03-planning-light.svg) · [dark](../../docs/assets/figures/03-planning-dark.svg) | STRIPS operator anatomy and the GPS means-ends recursion |
| [A* search](../../docs/assets/figures/04-astar-light.svg) · [dark](../../docs/assets/figures/04-astar-dark.svg) | f = g + h, the admissibility proof, and the strategy comparison |
| [Scenario, 30 nodes](../../docs/assets/figures/05-simulated-30-light.svg) · [dark](../../docs/assets/figures/05-simulated-30-dark.svg) | The `simulated` comparison scenario and the A* route across it |
| [Scenario, 60 nodes](../../docs/assets/figures/06-dual-60-light.svg) · [dark](../../docs/assets/figures/06-dual-60-dark.svg) | 15 dual-homed sites reached by both a pLTE star and a 900 MHz mesh |
| [State machine](../../docs/assets/figures/07-state-machine-light.svg) · [dark](../../docs/assets/figures/07-state-machine-dark.svg) | The restoration state space, and why the goal is unreachable while a fault is live |

O código deste experimento está em [`software/aisg/`](../../software/aisg/) (módulos `domain`, `expert_system`, `planning`, `search`) e os testes em [`software/tests/`](../../software/tests/). Ver [docs/architecture.md](../../docs/architecture.md).

The code for this experiment lives in [`software/aisg/`](../../software/aisg/) (modules `domain`, `expert_system`, `planning`, `search`) and the tests in [`software/tests/`](../../software/tests/). See [docs/architecture.md](../../docs/architecture.md).

## Cenário e premissas / Scenario and assumptions

O domínio é a rede de comunicação que liga ativos distribuídos de um sistema elétrico ao centro de operação: um núcleo em fibra, setores de rádio em 900 MHz, uma cadeia de repetidores *armazena-e-encaminha* e uma sobreposição de LTE privativo. Dois cenários estão disponíveis hoje:

The domain is the communication network linking distributed assets of an electric system to the operations centre: a fibre core, 900 MHz radio sectors, a *store-and-forward* relay chain, and a private LTE overlay. Two scenarios are available today:

| Cenário / Scenario | Nós / Nodes | Enlaces / Links | Uso / Use |
|---|---|---|---|
| `dual` (padrão / default) | 60 | 74 | 15 sites em duplo acesso; usado pelos comandos de exemplo abaixo (`aisg route --to ER_03`) e pelos experimentos 002–004 / 15 dual-homed sites; used by the example commands below (`aisg route --to ER_03`) and by experiments 002–004 |
| `simulated` | 30 | 44 | Três setores; usado especificamente para comparar o esforço de busca entre grafos de tamanhos diferentes (`aisg --topology simulated route --compare`) / three sectors; used specifically to compare search effort between graphs of different sizes |

**A topologia é SINTÉTICA.** É um modelo didático da *classe* de cenários estudada em laboratórios de pesquisa em backhaul sem fio. Não contém inventário real, endereçamento, identificação de equipamento, configuração de RF nem topologia de campo de qualquer laboratório ou concessionária. Ver [`docs/domain-model.md`](../../docs/domain-model.md).

**The topology is SYNTHETIC.** It is a didactic model of the *class* of scenarios studied in wireless backhaul research testbeds. It contains no real inventory, addressing, equipment identification, RF configuration, or field topology of any laboratory or utility. See [`docs/domain-model.md`](../../docs/domain-model.md).

**Simulado, e não de campo — por escolha metodológica.** O cenário é simulado, o que inverte a relação usual entre validade interna e externa a favor deste trabalho: uma condição de falha *comandada* é repetível e rotulável, ao passo que uma condição *observada* em campo é apenas provável. Cada diagnóstico declara, no bloco `INDUCIBLE_BY`, **como é induzido no simulador** — o que torna o conjunto de casos reprodutível por terceiros. O custo dessa escolha é explícito e está declarado: os resultados valem para o modelo, não para uma planta.

**Simulated rather than field, by methodological choice.** The scenario is simulated, which inverts the usual internal/external validity trade-off in this work's favor: a *commanded* fault condition is repeatable and labellable, whereas an *observed* field condition is merely probable. Each diagnosis declares in the `INDUCIBLE_BY` block **how it is induced in the simulator**, which makes the case set reproducible by third parties. The cost of that choice is explicit and declared: the results hold for the model, not for a plant.

**Premissa de modelagem.** `authorized(?n)` é precondição dos operadores que alteram o cenário, o que torna a restrição uma propriedade do espaço de estados em vez de uma verificação em tempo de execução — uma técnica de modelagem STRIPS, exercitada aqui sobre um cenário simulado.

**Modelling assumption.** `authorized(?n)` is a precondition of the operators that change the scenario, which makes the constraint a property of the state space rather than a runtime check — a STRIPS modelling technique, exercised here over a simulated scenario.

**Nota de proveniência.** Uma topologia de 17 nós existiu como cenário base até a v0.10.0 e foi removida junto com a base de conhecimento de campo (ver `CHANGELOG.md`); qualquer afirmação anterior ancorada nela deixou de ser reproduzível — ver [Limitações](#limitações--limitations).

**Provenance note.** A 17-node topology existed as the base scenario up to v0.10.0 and was removed together with the field knowledge base (see `CHANGELOG.md`); any earlier claim anchored to it is no longer reproducible — see [Limitations](#limitações--limitations).

## Software e versões / Software and versions

Não há dependências externas no núcleo: apenas a biblioteca padrão do Python 3.10+. `matplotlib` e `pytest` são extras de desenvolvimento/notebook, declarados em [`pyproject.toml`](../../pyproject.toml) (`pip install -e ".[dev]"`). Pacote `aisg`, versão 0.11.0.

The core has no third-party dependencies: only the Python 3.10+ standard library. `matplotlib` and `pytest` are development/notebook extras, declared in [`pyproject.toml`](../../pyproject.toml) (`pip install -e ".[dev]"`). Package `aisg`, version 0.11.0.

## Configuração / Configuration

**(i) Declaração de incerteza.** Todo limiar numérico usado por regra vive num único bloco (`SIM_THRESHOLDS`, em [`expert_system/`](../../software/aisg/expert_system/)) e está marcado como **nominal e não calibrado**. Nenhuma medição de laboratório o sustenta. A separação entre *estrutura* (as regras) e *parâmetro* (os limiares) é deliberada: a calibração futura ajusta valores sem reescrever conhecimento.

**(i) Declared uncertainty.** Every numeric threshold used by a rule lives in one block (`SIM_THRESHOLDS`, in [`expert_system/`](../../software/aisg/expert_system/)) and is marked **nominal and uncalibrated**. No laboratory measurement supports it. Separating *structure* (the rules) from *parameter* (the thresholds) is deliberate: future calibration adjusts values without rewriting knowledge.

**(ii) Verificação por oráculo independente.** Propriedades de correção não são argumentadas — são testadas contra um procedimento que **não compartilha código** com o artefato verificado. A otimalidade do A\* é conferida contra Floyd–Warshall; a consistência do domínio de planejamento, contra a análise por grafo de planejamento (Graphplan). Verificar o A\* com custo uniforme seria circular, pois `uniform_cost` é literalmente `astar` com `h = 0`.

**(ii) Verification by an independent oracle.** Correctness properties are not argued — they are tested against a procedure that **shares no code** with the artefact under test. A\*'s optimality is checked against Floyd–Warshall; the planning domain's consistency, against planning-graph (Graphplan) analysis. Checking A\* against uniform cost would be circular, since `uniform_cost` is literally `astar` with `h = 0`.

**(iii) Falseabilidade e resultado negativo.** O projeto registra o que **não** conseguiu demonstrar com o mesmo cuidado com que registra o que demonstrou — ver [Limitações](#limitações--limitations).

**(iii) Falsifiability and negative results.** The project records what it could **not** demonstrate as carefully as what it could — see [Limitations](#limitações--limitations).

## Dados de entrada / Input data

- Base de conhecimento simulada (`kb_simulated.py`): 41 regras de produção, 13 variáveis observáveis, fatores de certeza estilo MYCIN. / Simulated knowledge base (`kb_simulated.py`): 41 production rules, 13 observable variables, MYCIN-style certainty factors.
- 8 casos de diagnóstico simulados (p. ex. `rf_interference`, `mac_contention`, `congestion`), cada um com seu bloco `INDUCIBLE_BY`. / 8 simulated diagnosis cases (e.g. `rf_interference`, `mac_contention`, `congestion`), each with its own `INDUCIBLE_BY` block.
- Topologias declaradas em [`software/aisg/domain/data/`](../../software/aisg/domain/data/): `backhaul-topology-60.json` (`dual`) e `backhaul-topology-30.json` (`simulated`). / Topologies declared in [`software/aisg/domain/data/`](../../software/aisg/domain/data/): `backhaul-topology-60.json` (`dual`) and `backhaul-topology-30.json` (`simulated`).
- Domínio de planejamento STRIPS: operadores e precondições em [`planning/`](../../software/aisg/planning/), validados pela análise por grafo de planejamento — ver [`planner-design-process.md`](planner-design-process.md). / STRIPS planning domain: operators and preconditions in [`planning/`](../../software/aisg/planning/), validated by planning-graph analysis — see [`planner-design-process.md`](planner-design-process.md).

## Procedimento de execução / Execution procedure

```bash
git clone https://github.com/fsd-dantas/applied-ai-for-wireless-communication.git
cd applied-ai-for-wireless-communication
python -m pip install -e ".[dev]"

# 1 — sistema especialista / expert system
aisg diagnose --case rf_interference --trace --explain
aisg diagnose --interactive --mode backward      # consulta guiada por objetivo

# 2 — planejamento / planning
aisg plan --diagnosis mac_contention --node SAF_02 --solver both --trace

# 3 — busca A* / A* search
aisg route --from NOC --to ER_03 --compare --expansion

# os três em sequência / all three in sequence
aisg pipeline --case congestion --node SAF_01 --target ER_03

# comparação de esforço de busca entre grafos / search-effort comparison between graphs
aisg --topology simulated route --compare
```

Sem instalar / without installing: `PYTHONPATH=software python -m aisg ...`
Em inglês / in English: acrescente `--lang en` / add `--lang en`.

Fundamentos teóricos na wiki / theoretical foundations in the wiki: [github.com/fsd-dantas/applied-ai-for-wireless-communication/wiki](https://github.com/fsd-dantas/applied-ai-for-wireless-communication/wiki)

## Métricas / Metrics

| Métrica / Metric | Onde é usada / Where it is used |
|---|---|
| Fator de certeza (CF) da conclusão / Conclusion certainty factor (CF) | diagnóstico, comparação encadeamento progressivo × regressivo / diagnosis, forward vs backward chaining comparison |
| Regras disparadas, fatos consultados / Rules fired, facts consulted | custo do encadeamento / chaining cost |
| Custo do caminho, nós expandidos, gerados e pico da fronteira / Path cost, nodes expanded, generated and frontier peak | comparação entre estratégias de busca / search-strategy comparison |
| Validade do plano (execução passo a passo) / Plan validity (step-by-step replay) | correção do planejador / planner correctness |
| Exclusão mútua no ponto fixo, nível do objetivo / Mutual exclusion at the fixpoint, goal level | consistência do domínio de planejamento / planning-domain consistency |

## Resultados / Results

| Propriedade afirmada / Claimed property | Como é verificada / How it is checked | Oráculo / Oracle |
|---|---|---|
| O A\* devolve o caminho de custo mínimo / A\* returns the least-cost path | todos os pares ordenados, nos dois cenários / every ordered pair, both scenarios | Floyd–Warshall |
| A heurística é admissível e consistente / The heuristic is admissible and consistent | todos os pares ordenados / every ordered pair | comparação com o `h*` exato / comparison against exact `h*` |
| O plano é executável e atinge o objetivo / A plan is executable and reaches the goal | reexecução passo a passo desde o estado inicial / step-by-step replay from the initial state | `Plan.validate` |
| O domínio não declara sucesso sobre falha viva / The domain never declares success over a live fault | exclusão mútua no ponto fixo / mutual exclusion at the fixpoint | grafo de planejamento / planning graph |
| Nenhum operador é inalcançável / No operator is unreachable | presença nos níveis de ação / presence in the action levels | grafo de planejamento / planning graph |
| Limite inferior do tamanho do plano / Lower bound on plan length | nível do objetivo sem exclusão mútua / goal level free of mutexes | grafo de planejamento / planning graph |

São **254 testes** no repositório, que asseguram *propriedades* — admissibilidade, validade de plano, invariantes do domínio — e não apenas saídas esperadas.

There are **254 tests** in the repository, asserting *properties* — admissibility, plan validity, domain invariants — rather than merely expected outputs.

**A* expande menos nós que o custo uniforme.** A afirmação histórica de ganho em dois pontos (17 e 30 nós) não é reproduzível, pois o cenário de 17 nós foi removido na v0.10.0 (ver [Cenário e premissas](#cenário-e-premissas--scenario-and-assumptions)). A estatística agregada foi refeita sobre os cenários atuais, somando os nós expandidos em **todos** os pares ordenados: no `simulated` (30 nós, 870 pares) o A\* expande **25,9%** menos que o custo uniforme; no `dual` (60 nós, 3540 pares), **8,9%** menos. A vantagem **encolhe** conforme o grafo cresce — o oposto da intuição usual. Para um único par ilustrativo, `NOC → ER_03` no `dual`, são 23 nós contra 28 (17,9% a menos), ambos convergindo para o mesmo caminho de custo 360,35. A soma agregada agora é um teste de regressão — ver [`astar.md`](astar.md).

**A\* expands fewer nodes than uniform cost.** The historical two-point gain claim (17 and 30 nodes) is not reproducible, since the 17-node scenario was removed in v0.10.0 (see [Scenario and assumptions](#cenário-e-premissas--scenario-and-assumptions)). The aggregate statistic has been re-established on the current scenarios, summing expansions over **every** ordered pair: on `simulated` (30 nodes, 870 pairs) A\* expands **25.9%** fewer nodes than uniform cost; on `dual` (60 nodes, 3540 pairs), **8.9%** fewer. The advantage **shrinks** as the graph grows — the opposite of the usual intuition. For a single illustrative pair, `NOC → ER_03` on `dual`, it is 23 nodes against 28 (17.9% fewer), both converging on the same cost-360.35 path. The aggregate sum is now a regression test — see [`astar.md`](astar.md).

Documentação de apoio / supporting documentation:

| Documento / Document | Conteúdo / Contents |
|---|---|
| [`expert-system.md`](expert-system.md) | Variáveis, 41 regras na base simulada, fatores de certeza, encadeamentos, resolução de conflito, explicação / Variables, 41 rules in the simulated base, certainty factors, both chainings, conflict resolution, explanation |
| [`planning.md`](planning.md) | STRIPS, GPS e análise meios-fins, planejador A*, limitações do GPS / STRIPS, GPS and means-ends analysis, the A* planner, GPS's limitations |
| [`planner-design-process.md`](planner-design-process.md) | Como o domínio de planejamento foi definido, e a análise por grafo de planejamento que o valida / How the planning domain was defined, and the planning-graph analysis that validates it |
| [`astar.md`](astar.md) | A*, prova de admissibilidade e consistência, comparação entre estratégias / A*, admissibility and consistency proofs, strategy comparison |
| [`docs/domain-model.md`](../../docs/domain-model.md) | Topologia, modelo de custo e limites de validade / Topology, cost model, and validity limits |

## Limitações / Limitations

**GPS não-ótimo é uma propriedade real, mas este domínio não consegue exibi-la.** Nenhum literal tem mais de um operador que o produza, logo a análise meios-fins não tem escolha para errar. Ver [`planning.md`](planning.md).

**GPS non-optimality is a real property, yet this domain cannot exhibit it.** No literal has more than one producing operator, so means-ends analysis has no choice to get wrong. See [`planning.md`](planning.md).

Os limiares nominais (`SIM_THRESHOLDS`) não são calibrados por medição de laboratório; os resultados valem para o modelo simulado, não para uma planta real — ver [Cenário e premissas](#cenário-e-premissas--scenario-and-assumptions).

Nominal thresholds (`SIM_THRESHOLDS`) are not calibrated by laboratory measurement; results hold for the simulated model, not for a real plant — see [Scenario and assumptions](#cenário-e-premissas--scenario-and-assumptions).

## Estado de reprodutibilidade / Reproducibility status

**Reproduzível.** `python -m pytest` (ou `make check`) executa os 254 testes; o workflow [`tests.yml`](../../.github/workflows/tests.yml) roda a mesma suíte em CI a cada push/PR na `main`. Cada diagnóstico simulado declara `INDUCIBLE_BY`, o que torna o conjunto de casos reproduzível por terceiros sem acesso a nenhum laboratório.

**Reproducible.** `python -m pytest` (or `make check`) runs the 254 tests; the [`tests.yml`](../../.github/workflows/tests.yml) workflow runs the same suite in CI on every push/PR to `main`. Every simulated diagnosis declares `INDUCIBLE_BY`, which makes the case set reproducible by third parties with no access to any laboratory.

## Material de manuscrito relacionado / Related manuscript material

- [`literature/systematic-review/al-ajlan-2015/`](../../literature/systematic-review/al-ajlan-2015/) — análise crítica que mede encadeamento progressivo × regressivo sobre esta mesma base de 41 regras / critical analysis measuring forward vs backward chaining over this same 41-rule base.
- `manuscripts/presentations/` — deck, roteiro de fala e notebook de apresentação: locais, não publicados neste repositório; a wiki é a companhia pública. / deck, speaking script and presentation notebook: local, not published in this repository; the wiki is the public companion.

---

## Referências / References

- FIKES, R. E.; NILSSON, N. J. STRIPS: a new approach to the application of theorem proving to problem solving. *Artificial Intelligence*, v. 2, n. 3-4, p. 189-208, 1971.
- NEWELL, A.; SIMON, H. A. *GPS, a program that simulates human thought*. Santa Monica: RAND Corporation, 1961.
- HART, P. E.; NILSSON, N. J.; RAPHAEL, B. A formal basis for the heuristic determination of minimum cost paths. *IEEE Transactions on Systems Science and Cybernetics*, v. 4, n. 2, p. 100-107, 1968.
- SHORTLIFFE, E. H.; BUCHANAN, B. G. A model of inexact reasoning in medicine. *Mathematical Biosciences*, v. 23, n. 3-4, p. 351-379, 1975.
- TURING, A. M. Computing machinery and intelligence. *Mind*, v. LIX, n. 236, p. 433-460, 1950.
- RUSSELL, S.; NORVIG, P. *Artificial intelligence*: a modern approach. 4. ed. Harlow: Pearson, 2021.

## Como citar / How to cite

Use [`CITATION.cff`](../../CITATION.cff). No GitHub, o botão **Cite this repository** gera BibTeX e APA a partir dele.
Use [`CITATION.cff`](../../CITATION.cff). On GitHub, the **Cite this repository** button generates BibTeX and APA from it.

## Autor / Author

Fernando Sabino Dantas — trabalhos práticos da disciplina de Introdução à Inteligência Artificial (mestrado/doutorado).
Practical assignments for the Introduction to Artificial Intelligence course (MSc/PhD).

## Licença / License

[MIT](../../LICENSE).
