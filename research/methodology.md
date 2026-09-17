# Metodologia / Methodology

## Compromissos declarados / Declared commitments

**(i) Declaração de incerteza / Declared uncertainty.** Todo limiar numérico usado por regra vive num único bloco e está marcado como **nominal e não calibrado**. Estrutura (as regras) e parâmetro (os limiares) ficam separados: calibrar ajusta valores sem reescrever conhecimento.
Every numeric threshold a rule uses lives in one block, marked **nominal and uncalibrated**. Structure (the rules) and parameter (the thresholds) are kept apart: calibration adjusts values without rewriting knowledge.

**(ii) Verificação por oráculo independente / Verification by an independent oracle.** Propriedades de correção são testadas contra procedimentos que **não compartilham código** com o artefato verificado — por exemplo, a otimalidade do A\* contra Floyd–Warshall.
Correctness properties are tested against procedures that **share no code** with the artefact under test — for example, A\* optimality against Floyd–Warshall.

**(iii) Falseabilidade e resultado negativo / Falsifiability and negative results.** O que não foi possível demonstrar é registrado com o mesmo cuidado do que foi demonstrado.
What could not be demonstrated is recorded as carefully as what could.

## Cenários sintéticos / Synthetic scenarios

Os cenários são simulados por escolha metodológica: uma falha **comandada** é repetível e rotulável; uma falha **observada** em campo é apenas provável. Cada diagnóstico declara como é induzido no simulador. O custo é explícito: os resultados valem para o modelo, não para uma planta.

Scenarios are simulated by methodological choice: a **commanded** fault is repeatable and labellable; a fault **observed** in the field is merely probable. Every diagnosis declares how it is induced in the simulator. The cost is explicit: results hold for the model, not for a plant.

**A verdade comandada serve só para avaliar.** Nenhum componente de decisão lê a falha que o cenário comandou; ela é usada exclusivamente para pontuar o resultado.
**Commanded ground truth is for scoring only.** No decision component reads the fault a scenario commanded; it is used exclusively to score the result.

## Sequência dos experimentos / Experiment sequence

A ordem 001 → 002 → 003 → 004 é consequência da primeira restrição do problema, e não uma cronologia de conveniência. Sem dados rotulados de falha, o conhecimento não pode ser aprendido: precisa ser **codificado** (001) e depois dividido e coordenado (002, 003). Verificar essa codificação exige casos **rotuláveis e repetíveis**, que uma rede de campo não oferece e que um simulador só oferece quando a falha é **comandada** — daí os casos declarados que alimentam 001–003.

O experimento 004 é o **experimento integrador**: recebe dos anteriores as falhas a induzir e o plano a aplicar, e fornece o que casos declarados não podem fornecer — uma planta onde as consequências são **calculadas**, e não afirmadas. É necessariamente o último, porque depende da saída dos outros três.

O ciclo fecha na direção inversa para o quadro-negro: `aisg ns3-diagnose` diagnostica a partir de `nodes.csv` sem ler a falha comandada, e a [repetição causal](../experiments/004-multi-rat-simulation/telemetry-replay.md) aplica as decisões inferidas e mede a recuperação. Hoje esse retorno cobre um cenário e um tipo de decisão; 001 e 003 continuam sobre casos declarados.

The order 001 → 002 → 003 → 004 follows from the problem's first constraint, not from convenience. With no labelled fault data the knowledge cannot be learned: it must be **encoded** (001), then split and coordinated (002, 003). Checking that encoding needs **labellable, repeatable** cases, which a field network cannot give and which a simulator gives only when the fault is **commanded** — hence the declared cases feeding 001–003.

Experiment 004 is the **integrating experiment**: it receives the faults to induce and the plan to apply from the earlier ones, and supplies what declared cases cannot — a plant where consequences are **computed** rather than asserted. It is necessarily last, because it depends on the other three's output.

The loop closes in the reverse direction for the blackboard: `aisg ns3-diagnose` diagnoses from `nodes.csv` without reading the commanded fault, and the [causal replay](../experiments/004-multi-rat-simulation/telemetry-replay.md) applies the inferred decisions and measures recovery. Today that return path covers one scenario and one decision type; 001 and 003 still run on declared cases.

## Estratégia de validação / Validation strategy

| Propriedade / Property | Verificação / Check | Oráculo / Oracle | Exp. |
|---|---|---|---|
| O A\* devolve o caminho de custo mínimo / A\* returns the least-cost path | todos os pares, dois cenários / every pair, both scenarios | Floyd–Warshall | 001 |
| A heurística é admissível e consistente / The heuristic is admissible and consistent | todos os pares / every pair | `h*` exato / exact `h*` | 001 |
| O plano é executável e atinge o objetivo / A plan is executable and reaches the goal | reexecução passo a passo / step-by-step replay | `Plan.validate` | 001 |
| O domínio não declara sucesso sobre falha viva / The domain never declares success over a live fault | exclusão mútua no ponto fixo / mutex at the fixpoint | grafo de planejamento / planning graph | 001 |
| Dividir a base em especialistas não muda conclusões / Splitting the base into experts changes no conclusion | 8 casos, todos os objetivos, CF idêntico / 8 cases, every goal, identical CF | base única / single base | 002 |
| Uma causa comum explica as interrupções a jusante / One common cause explains the downstream outages | conjuntos escritos à mão / hand-written sets | alcançabilidade por BFS / BFS reachability | 002 |
| O controlador chega à quiescência / The controller reaches quiescence | segunda execução sem agenda / second pass with an empty agenda | ponto fixo / fixpoint | 002 |

## Estrutura de um experimento / Experiment structure

Cada experimento declara sua questão, o método, como executar e como os resultados são verificados, no seu `README.md`. Ver [CONTRIBUTING.md](../CONTRIBUTING.md).
Every experiment states its question, method, how to run it and how its results are checked, in its `README.md`. See [CONTRIBUTING.md](../CONTRIBUTING.md).
