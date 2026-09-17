# Roteiro / Roadmap

Pastas são criadas quando recebem conteúdo; este roteiro registra o que está planejado.
Folders are created when they receive content; this roadmap records what is planned.

## Experimentos / Experiments

| # | Experimento / Experiment | Estado / Status |
|---|---|---|
| 001 | Encadeamento simbólico diagnóstico → plano → rota / Symbolic diagnosis → plan → route chain | concluído / complete |
| 002 | Sistema multiespecialista com quadro-negro / Multi-expert blackboard | concluído / complete |
| 003 | Eco-resolução: agentes reativos em conflito por recursos da rede multi-RAT / Eco-resolution: reactive agents in conflict over multi-RAT network resources | concluído no modelo / complete on the model |
| 004 | Simulação multi-RAT em ns-3 (LTE privativo + 900 MHz) com injeção de falhas e verificação / Multi-RAT ns-3 simulation (private LTE + 900 MHz) with fault injection and verification | concluído no modelo / complete on the model |

## Simulador / Simulator (experiment 004)

| Etapa / Step | Descrição / Description |
|---|---|
| Gerador de cenário / Scenario generator | topologia declarada → cenário ns-3 / declared topology → ns-3 scenario |
| LTE privativo / Private LTE | módulo LTE com EPC; banda 31 (450 MHz) acrescentada à tabela EARFCN / LTE module with EPC; band 31 (450 MHz) added to the EARFCN table |
| 900 MHz | abstração declarada de rádio armazena-e-encaminha / declared store-and-forward radio abstraction |
| Tráfego / Traffic | SCADA, comandos, leitura de medição, firmware (padrões de tráfego) / SCADA, commands, meter reads, firmware (traffic patterns) |
| Falhas / Faults | parada de nó, interferência, congestionamento / node stop, interference, congestion |
| Telemetria / Telemetry | exportação para registros de observação / export to observation records |
| Failover | local no roteador de borda e central no centro de operação / local at the edge router and central at the operations centre |
| Verificação / Verification | execução de resolução e animação / resolution run and animation |

## Conformidade e verificação / Conformance and verification

O vocabulário de diagnósticos tem um único dono (`INDUCIBLE_BY`, na base de conhecimento), mas cada consumidor — planejador, quadro-negro, eco-resolução, exportador ns-3 — mantém a sua própria cópia. Os itens abaixo transformam essa coerência, hoje mantida à mão, em verificação automática.

The diagnosis vocabulary has a single owner (`INDUCIBLE_BY`, in the knowledge base), yet every consumer — planner, blackboard, eco-resolution, ns-3 exporter — keeps its own copy. The items below turn that coherence, today maintained by hand, into an automated check.

| Item | Descrição / Description |
|---|---|
| Teste de conformidade do vocabulário / Vocabulary conformance test | garantir que `DIAGNOSIS_TO_FAULT`, `FAULT_BY_DIAGNOSIS` e as partições dos experimentos 002 e 003 cobrem `INDUCIBLE_BY`, com isenções declaradas (`healthy` nunca é comandado) / assert that `DIAGNOSIS_TO_FAULT`, `FAULT_BY_DIAGNOSIS` and the 002/003 partitions cover `INDUCIBLE_BY`, with declared exemptions (`healthy` is never commanded) |
| Induzir `mac_contention` e `routing_misconfiguration` / Inducing them in the simulator | sem mecanismo em `FAULT_BY_DIAGNOSIS` hoje; exigiria um PHY/MAC com contenção no lugar da abstração ponto a ponto de 900 MHz / no mechanism today; would need a contention-capable PHY/MAC in place of the 900 MHz point-to-point abstraction |
| Separar `rf_interference` de `excess_path_loss` no simulador / Separating them in the simulator | ambos são induzidos pelo mesmo `radio_per`, então uma execução não distingue o que as regras separam / both are induced by the same `radio_per`, so a run cannot distinguish what the rules separate |
| Classificar `routing_misconfiguration` em 002 e 003 / Classifying it in 002 and 003 | não aparece em nenhuma partição, então um nó assim continua utilizável como trânsito na rota A\* / it appears in no partition, so such a node stays usable as A\* transit |
| Estatística agregada do A\* / Aggregate A\* statistic | script ou teste que recalcule os nós expandidos sobre todos os pares ordenados dos dois cenários; os valores atuais (25,9% em 30 nós, 8,9% em 60) não são reproduzíveis por nenhum comando do repositório / a script or test recomputing expansions over every ordered pair in both scenarios; today's figures (25.9% at 30 nodes, 8.9% at 60) are reproducible by no command here |

A exportação da telemetria simulada como registros de observação — o passo que fecha o ciclo diagnóstico → plano → verificação — está registrada acima, em [Simulador](#simulador--simulator-experiment-004).
Exporting simulated telemetry as observation records — the step that closes the diagnosis → plan → verification loop — is recorded above, under [Simulador](#simulador--simulator-experiment-004).

## Revisão de literatura / Literature review (`literature/`)

`literature/systematic-review/` guarda uma pasta por artigo revisado; hoje contém apenas `al-ajlan-2015/`. Os demais arquivos abaixo entram quando tiverem conteúdo real.
`literature/systematic-review/` holds one folder per reviewed paper; today it holds only `al-ajlan-2015/`. The files below arrive once they carry real content.

| Arquivo planejado / Planned file | Conteúdo / Contents |
|---|---|
| `review-protocol.md` | protocolo da revisão sistemática (pergunta, método, papéis) / systematic review protocol (question, method, roles) |
| `search-strategy.md` | bases de dados, strings de busca, período / databases, search strings, date range |
| `inclusion-exclusion-criteria.md` | critérios de inclusão e exclusão / inclusion and exclusion criteria |
| `evidence-matrix.csv` | matriz de evidência por artigo revisado / evidence matrix per reviewed paper |
| `annotated-bibliography.md` | bibliografia anotada, um resumo por referência / annotated bibliography, one summary per reference |

## Tópicos de literatura planejados / Planned literature topics

Smart-grid architectures · utility communications · LTE and private LTE · band 31 and 900 MHz · SDN and NFV · network resilience · machine learning for networks · fuzzy logic · ICCP and grid protocols · network simulation.
