# Contrato de diagnóstico / Diagnosis contract

`software/aisg/domain/diagnoses.py` é o dono dos oito identificadores de diagnóstico e das capacidades atuais de cada um. O registro e os seus registros são imutáveis. Use `diagnosis_contract(name)` para consulta: nomes desconhecidos levantam `ValueError` em vez de serem tratados como nó saudável.

`software/aisg/domain/diagnoses.py` owns the eight diagnosis identifiers and their current capabilities. The registry and its records are immutable. Use `diagnosis_contract(name)` for lookup: unknown names raise `ValueError` rather than being treated as a healthy node.

`healthy` significa ausência de falha; `unsupported` significa uma lacuna explícita, nunca um nó saudável. Receitas de indução descrevem experimentos pretendidos e não garantem suporte no exportador ns-3.

`healthy` means the absence of a fault; `unsupported` means an explicit gap, never a healthy node. Induction recipes describe intended experiments and do not imply support in the ns-3 exporter.

| Diagnosis | Planner fault | Blackboard routing | Eco-resolution | ns-3 injection |
|---|---|---|---|---|
| `rf_interference` | `interference` | Avoid if possible | Degraded | Approximate: `radio_per` |
| `excess_path_loss` | `excess-path-loss` | Avoid if possible | Degraded | Approximate: same `radio_per` |
| `mac_contention` | `mac-contention` | Avoid if possible | Degraded | Unsupported: no contention MAC |
| `node_failure` | `node-stopped` | Exclude | Down | `node_down` |
| `upstream_relay_failure` | `relay-down` | Exclude | Down | `node_down` |
| `routing_misconfiguration` | `route-missing` | Exclude | Degraded | Unsupported: no route injection |
| `congestion` | `congested` | Exclude | Reduced capacity | `flood`, eNodeB targets only |
| `healthy` | None needed | No restriction | No restriction | Baseline, no fault command |

Só as falhas de nó e de repetidor a montante participam como interrupções na correlação por causa comum. Roteamento e eco-resolução têm, deliberadamente, políticas diferentes para congestionamento e para roteamento: um nó mal configurado responde, então a eco-resolução o registra como degradado e não como parado, enquanto o roteamento o exclui por completo — atravessá-lo descarta o tráfego em vez de atrasá-lo, o que torna «evitar se possível» insuficiente. Como `usable` reúne nós parados e degradados, os dois rótulos proíbem igualmente o caminho.

Only node and upstream-relay failures participate as outages in common-cause correlation. Routing and eco-resolution deliberately differ on congestion and on routing: a misconfigured node answers, so eco-resolution records it as degraded rather than down, while routing excludes it outright — crossing it discards traffic instead of slowing it, which makes "avoid if possible" insufficient. Since `usable` unions stopped and degraded nodes, both labels forbid the path equally.

## Mecanismos de injeção / Injection mechanisms

`FaultMechanism` é um conjunto **fechado**: `node_down`, `radio_per`, `flood`. Um mecanismo fora dessa lista não entra num contrato; um mecanismo listado mas sem ramo correspondente em `_add_faults` faz o exportador levantar `ScenarioError`. As duas metades importam — antes, uma string plausível atravessava o exportador, não casava com nenhum ramo e produzia um cenário **sem falha alguma**, que era então comparado com previsões que esperavam uma.

`FaultMechanism` is a **closed** set: `node_down`, `radio_per`, `flood`. A mechanism outside it cannot enter a contract; a mechanism listed there without a matching branch in `_add_faults` makes the exporter raise `ScenarioError`. Both halves matter — previously a plausible-looking string passed through the exporter, matched no branch, and produced a scenario with **no fault in it at all**, which was then scored against predictions expecting one.

## Compatibilidade e escopo / Compatibility and scope

`INDUCIBLE_BY`, `DIAGNOSIS_TO_FAULT`, `FAULT_BY_DIAGNOSIS` e as partições do quadro-negro e da eco-resolução mantêm os seus caminhos de importação e são derivados do contrato. São visões de compatibilidade: edite o registro, não as visões.

`INDUCIBLE_BY`, `DIAGNOSIS_TO_FAULT`, `FAULT_BY_DIAGNOSIS` and the blackboard/eco partitions keep their existing import paths and are derived from the contract. They are compatibility views; edit the registry rather than the views.

Este contrato registra o comportamento atual. Tratamento pelos consumidores e indução no simulador são independentes: o roteamento e a eco-resolução já excluem do trânsito um nó com `routing_misconfiguration`, mas o exportador ns-3 continua sem saber remover ou desviar uma rota, de modo que a falha não pode ser produzida numa execução. Essa lacuna está registrada na capacidade de simulação, e não como `handling_gap` — que fica reservado ao caso em que um consumidor ignora o diagnóstico. O contrato também não calibra fatores de certeza nem fecha o ciclo de realimentação do simulador; ambos estão em [`research/roadmap.md`](../research/roadmap.md).

This contract records current behaviour. Consumer handling and simulator induction are independent: routing and eco-resolution now exclude a node diagnosed `routing_misconfiguration` from transit, but the ns-3 exporter still cannot remove or misdirect a route, so the fault cannot be produced in a run. That gap is recorded on the simulation capability rather than as a `handling_gap`, which is reserved for a consumer that ignores the diagnosis. Nor does the contract calibrate certainty factors or close the simulator feedback loop; both are in [`research/roadmap.md`](../research/roadmap.md).

## O que os testes garantem / What the tests guarantee

`test_diagnoses.py` cobre a cobertura do vocabulário, o tratamento da linha de base e as lacunas declaradas. Vale saber o que é e o que não é verificação real: como as visões são **derivadas** do registro, compará-las com ele não pode falhar. As verificações genuinamente independentes são três — o conjunto de casos `SIM_CASES`, escrito à mão; a correspondência entre cada `planner_fault` e o operador que o limpa; e a correspondência entre cada mecanismo e o ramo do exportador que o despacha.

`test_diagnoses.py` covers vocabulary coverage, baseline handling and declared gaps. It is worth knowing which parts are real verification: because the views are **derived** from the registry, comparing them against it cannot fail. Three checks are genuinely independent — the hand-written `SIM_CASES` fixture, the correspondence between each `planner_fault` and the operator that clears it, and the correspondence between each mechanism and the exporter branch that dispatches it.

## Acrescentar um diagnóstico / Adding a diagnosis

1. Acrescente um contrato com literal de reparo, efeito de roteamento, efeito na eco-resolução, classificação de correlação, receita de indução e capacidade de simulação. / Add a contract with a repair literal, routing effect, eco effect, correlation classification, induction recipe and simulator capability.
2. Explique lacunas e aproximações explicitamente. Reserve `planner_fault = None` para `healthy`. / Explain gaps and approximations explicitly. Reserve `planner_fault = None` for `healthy`.
3. Implemente as regras e o caso da base de conhecimento, o operador que limpa o literal de reparo, e qualquer suporte de consumidor ou simulador declarado. Um mecanismo novo exige **um membro de `FaultMechanism` e um ramo em `_add_faults`** — um sem o outro falha os testes. Uma entrada no contrato, por si só, não implementa nada disso. / Implement the knowledge-base rules and fixture, the operator that clears the repair literal, and any claimed consumer or simulator support. A new mechanism needs **both a `FaultMechanism` member and a branch in `_add_faults`** — one without the other fails the tests. A contract entry alone implements none of this.
4. Rode `python -m pytest`. / Run `python -m pytest`.
