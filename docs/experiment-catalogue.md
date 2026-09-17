# Catálogo de experimentos / Experiment catalogue

A rede simulada vem primeiro: é a linha de base sobre a qual os outros três operam. A numeração segue a ordem de construção; as questões RQ1–RQ6 seguem a ordem de investigação.

The simulated network comes first: it is the baseline the other three run on. The numbering follows the order they were built in; the questions RQ1–RQ6 follow the order they were investigated in.

| # | Experimento / Experiment | Questão / Question | Métodos / Methods | Entrada / Entry point | Estado / Status |
|---|---|---|---|---|---|
| 004 | [Simulação multi-RAT / Multi-RAT simulation](../experiments/004-multi-rat-simulation/) | RQ6 | ns-3: LTE privativo, 900 MHz, injeção de falhas / ns-3: private LTE, 900 MHz, fault injection | `aisg ns3-export` + `dual-homed-backhaul` | concluído no modelo / complete on the model |
| 001 | [Encadeamento simbólico de restauração / Symbolic restoration chain](../experiments/001-symbolic-restoration-chain/) | RQ1–RQ3 | Regras de produção com fatores de certeza; STRIPS e GPS; A\* / Production rules with certainty factors; STRIPS and GPS; A\* | `aisg pipeline` | concluído / complete |
| 002 | [Quadro-negro multiespecialista / Multi-expert blackboard](../experiments/002-multi-expert-blackboard/) | RQ4 | Arquitetura blackboard, correlação de incidentes, failover multi-RAT / Blackboard architecture, incident correlation, multi-RAT failover | `aisg blackboard` | concluído / complete |
| 003 | [Eco-resolução / Eco-resolution](../experiments/003-eco-resolution/) | RQ5 | Agentes reativos: satisfação, agressão, fuga, dependência / Reactive agents: satisfaction, aggression, flight, dependency | `aisg eco` | concluído no modelo / complete on the model |
