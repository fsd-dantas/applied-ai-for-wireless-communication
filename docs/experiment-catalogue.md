# Catálogo de experimentos / Experiment catalogue

| # | Experimento / Experiment | Questão / Question | Métodos / Methods | Entrada / Entry point | Estado / Status |
|---|---|---|---|---|---|
| 001 | [Encadeamento simbólico de restauração / Symbolic restoration chain](../experiments/001-symbolic-restoration-chain/) | RQ1–RQ3 | Regras de produção com fatores de certeza; STRIPS e GPS; A\* / Production rules with certainty factors; STRIPS and GPS; A\* | `aisg pipeline` | concluído / complete |
| 002 | [Quadro-negro multiespecialista / Multi-expert blackboard](../experiments/002-multi-expert-blackboard/) | RQ4 | Arquitetura blackboard, correlação de incidentes, failover multi-RAT / Blackboard architecture, incident correlation, multi-RAT failover | `aisg blackboard` | concluído / complete |
| 003 | [Eco-resolução / Eco-resolution](../experiments/003-eco-resolution/) | RQ5 | Agentes reativos: satisfação, agressão, fuga, dependência / Reactive agents: satisfaction, aggression, flight, dependency | `aisg eco` | concluído no modelo / complete on the model |
| 004 | [Simulação multi-RAT / Multi-RAT simulation](../experiments/004-multi-rat-simulation/) | RQ6 | ns-3: LTE privativo, 900 MHz, injeção de falhas; diagnóstico a partir da telemetria medida / ns-3: private LTE, 900 MHz, fault injection; diagnosis from measured telemetry | `aisg ns3-export` + `dual-homed-backhaul`, `aisg ns3-diagnose` | concluído no modelo / complete on the model |

Os experimentos 001–003 raciocinam sobre **casos declarados** — falhas comandadas, repetíveis e rotuláveis, exigidas pela ausência de dados rotulados de falha. O 004 é o **experimento integrador**: recebe deles as falhas a induzir e o plano central a aplicar, e devolve medição; `aisg ns3-diagnose` fecha o ciclo no sentido inverso, diagnosticando a partir da telemetria sem ler a falha comandada. Ver o encadeamento no [README](../README.md#como-os-experimentos-se-encadeiam--how-the-experiments-chain) e a justificativa da ordem em [`research/methodology.md`](../research/methodology.md).

Experiments 001–003 reason over **declared cases** — commanded, repeatable, labellable faults, required by the absence of labelled fault data. 004 is the **integrating experiment**: it receives the faults to induce and the central plan to apply, and returns measurement; `aisg ns3-diagnose` closes the loop the other way, diagnosing from telemetry without reading the commanded fault. See the chain in the [README](../README.md#como-os-experimentos-se-encadeiam--how-the-experiments-chain) and the order's justification in [`research/methodology.md`](../research/methodology.md).

Até onde esse encadeamento é realmente executável está registrado na [matriz de capacidades](capability-matrix.md): quais observações o simulador mede, quais intervenções ele sabe aplicar, e onde as demonstrações autônomas continuam valendo apenas como testes de componente.

How far that chain is actually executable is recorded in the [capability matrix](capability-matrix.md): which observations the simulator measures, which interventions it can apply, and where the standalone demonstrations still hold only as component tests.
