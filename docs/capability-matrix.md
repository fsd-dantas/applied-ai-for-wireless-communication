# Matriz de capacidades / Capability matrix

O que cada experimento **precisa observar** e **precisa executar**, contra o que o simulador do [experimento 004](../experiments/004-multi-rat-simulation/) realmente oferece. O objetivo é expor as lacunas antes de construir mais integração sobre suposições incompletas.

What each experiment **needs to observe** and **needs to execute**, against what the [experiment 004](../experiments/004-multi-rat-simulation/) simulator actually provides. The purpose is to expose the gaps before more integration is built on incomplete assumptions.

Todos os números abaixo são derivados do código, não estimados: `NS3_PARAMETERS`, `ECO_NETWORK_PARAMETERS`, `build_operators()`, `FaultMechanism` e a gramática `.scn`.

Every figure below is derived from code, not estimated: `NS3_PARAMETERS`, `ECO_NETWORK_PARAMETERS`, `build_operators()`, `FaultMechanism` and the `.scn` grammar.

## Resumo / Summary

| | Necessário / Required | Suportado / Supported |
|---|---|---|
| Observações por nó / Per-node observations | 13 | 4 medidas ou derivadas / measured or derived |
| Intervenções do planejador / Planner interventions | 7 | **0** |
| Decisões do quadro-negro / Blackboard decisions | 1 acionável / actionable | 1 |
| Movimentos de eco-resolução / Eco moves | 2 tipos / kinds | **0** (não expressáveis / not expressible) |
| Ações executáveis no simulador / Executable simulator actions | — | 1: `failover` |

A superfície de atuação do simulador é **uma única ação**. A gramática `.scn` admite apenas dois registros executáveis: `fault` (conjunto fechado: `node_down`, `radio_per`, `flood`) e `failover <t> <er> <medium>`. Nada mais em `main()` atua sobre a rede.

The simulator's actuation surface is **a single action**. The `.scn` grammar admits only two executable records: `fault` (a closed set: `node_down`, `radio_per`, `flood`) and `failover <t> <er> <medium>`. Nothing else in `main()` acts on the network.

## 1. Observações / Observations

As treze variáveis perguntáveis da base de conhecimento, e o que o simulador mede.

The knowledge base's thirteen askable variables, and what the simulator measures.

| Observation | Needed by | Support | How, or why not |
|---|---|---|---|
| `node_responding` | 001, 002 | **Measured** | `nodes.csv`: `heartbeats_received > 0` |
| `packet_loss_pct` | 001, 002 | **Measured** | `nodes.csv` per node; `sites.csv` per site |
| `upstream_relay_reachable` | 001, 002 | **Derived** | upstream's own count + declared topology |
| `neighbours_affected` | 001, 002 | **Derived** | neighbours' counts + declared topology |
| `rtt_ms` | 001, 002 | **Available, unused** | `requests.csv` carries per-poll RTT for all 15 sites; the adapter declares it unavailable for every subject |
| `rssi_dbm` | 001 (S01–S04) | Not supported | 900 MHz hops are `PointToPoint`; no receiver reports power |
| `snr_db` | 001 (S01–S04) | Not supported | same abstraction; no per-frame SNR |
| `excess_path_loss_db` | 001 (S12, S13, S23) | Not supported | a declared scenario parameter, not a measurement |
| `retry_rate_pct` | 001 (S14, S15, S25) | Not supported | no contention MAC exists to count retries |
| `offered_load_pct` | 001 (S20, S21) | Not supported | no declared per-node capacity as denominator |
| `route_present` | 001 (S19) | Not supported | no routing-table export |
| `co_channel_emitter` | 001 (S10, S11, S24) | Not supported | no emitter inventory is simulated |
| `nodes_sharing_channel` | 001 (S15) | Not supported | every radio hop is a dedicated link |

**Consequência imediata.** `signal_quality` depende de `rssi_dbm` e `snr_db`, e S22 (`healthy`) depende de `signal_quality`. Portanto **nenhum nó pode ser diagnosticado como saudável a partir de telemetria** — o correlacionador nunca vê um nó marcado como são, e nós saudáveis permanecem elegíveis para serem culpados como causa comum. Hoje isso é salvo apenas pelo desempate por profundidade.

**Immediate consequence.** `signal_quality` depends on `rssi_dbm` and `snr_db`, and S22 (`healthy`) depends on `signal_quality`. So **no node can be diagnosed healthy from telemetry** — the correlator never sees a node marked sound, and healthy nodes stay eligible to be blamed as a common cause. Today only the depth tie-break prevents that.

Medido na execução versionada `saf-chain-outage/none`, 52 nós: **zero** entradas de `signal_quality` e **zero** hipóteses de `healthy`. As únicas hipóteses de diagnóstico são `node_failure` (52 entradas — 18 positivas por S16, 34 negativas pela contraevidência S26) e `upstream_relay_failure` (17, o conjunto preso menos o próprio `SAF_02`, cujo salto a montante responde).

Measured on the versioned `saf-chain-outage/none` run, 52 nodes: **zero** `signal_quality` entries and **zero** `healthy` hypotheses. The only diagnosis hypotheses are `node_failure` (52 entries — 18 positive from S16, 34 negative from S26's counter-evidence) and `upstream_relay_failure` (17, the stranded set minus `SAF_02` itself, whose upstream answers).

**Ganho barato.** `rtt_ms` já é medido por site em `requests.csv` e `sites.csv`. Ligá-lo aos quinze sujeitos `ER_xx` torna S07 e S08 disponíveis, e portanto `link_symptom` concluível. Não desbloqueia `healthy`, que continua preso a `signal_quality`.

**Cheap win.** `rtt_ms` is already measured per site in `requests.csv` and `sites.csv`. Wiring it to the fifteen `ER_xx` subjects makes S07 and S08 available, and `link_symptom` concludable. It does **not** unlock `healthy`, which stays blocked on `signal_quality`.

### Observações da eco-resolução / Eco-resolution observations

Os agentes do experimento 003 não observam o simulador: observam o quadro do experimento 002 e o próprio mundo eco.

Experiment 003's agents do not observe the simulator: they observe experiment 002's board and the eco world itself.

| Agent observation | Source | Locality |
|---|---|---|
| `world.usable(site, medium)` | `down` / `degraded`, from 002's incidents | **Global, instantaneous** |
| `world.occupants(resource)` | every flow's assignment, network-wide | **Global, instantaneous** |
| `world.capacities[resource]` | declared constants | Global |
| `world.assignment[flow]` | every other agent's position | **Global, instantaneous** |

Cada agente enxerga o mundo inteiro, sem atraso e sem incerteza. Não há noção de alcance, de vizinhança nem de evidência parcial. Definir o que um agente pode observar e controlar é, hoje, uma lacuna aberta.

Every agent sees the whole world, with no delay and no uncertainty. There is no notion of range, neighbourhood or partial evidence. Defining what an agent may observe and control is, today, an open gap.

## 2. Ações / Actions

### Experimento 001 — planejador STRIPS / STRIPS planner

Treze operadores. Sete são intervenções na rede; seis não são.

Thirteen operators. Seven are network interventions; six are not.

| Operator | Kind | Simulator operation | Status |
|---|---|---|---|
| `restart_node` | intervention | — | **Not supported.** `node_down` is `ipv4->SetDown(i)`; there is no inverse |
| `restore_relay` | intervention | — | **Not supported.** Same mechanism on an upstream relay |
| `fix_routing` | intervention | — | **Not supported.** No route mutation exists; the fault cannot be injected either |
| `change_channel` | intervention | — | **Not supported.** No channel model on a point-to-point radio |
| `separate_channels` | intervention | — | **Not supported.** No channel plan to separate |
| `restore_path_budget` | intervention | — | **Not supported**, but mechanically reachable: `RateErrorModel::SetRate` already exists for `radio_per` |
| `reroute_traffic` | intervention | `failover` (partial) | **Semantic mismatch.** The planner diverts traffic *around a congested node*; `failover` switches *a site's access medium* |
| `stop_run`, `start_run` | run lifecycle | — | **Incoherent under live control.** These model stopping the experiment run, not a network operation |
| `verify_link` | bookkeeping | — | **Symbolic only.** Adds `link-up(?n)` by fiat once the `cleared-…` literals hold; consults no telemetry |
| `request_authorization` | governance | — | No network effect by design |
| `record_logbook`, `close_work_order` | bookkeeping | — | No network effect by design |

`restart_node` é a ação recomendada para `node_failure` — exatamente o diagnóstico que o ciclo fechado demonstrou de ponta a ponta. **O simulador não consegue executar o reparo da única falha que sabemos diagnosticar.** A repetição causal funcionou porque a troca de meio do árbitro é a única intervenção que a planta implementa.

`restart_node` is the recommended action for `node_failure` — precisely the diagnosis the closed loop demonstrated end to end. **The simulator cannot execute the repair for the one fault we can diagnose.** The causal replay worked because the arbiter's medium switch is the only intervention the plant implements.

### Experimento 002 — quadro-negro / blackboard

| Decision | Simulator operation | Status |
|---|---|---|
| `switch_medium` | `failover <t> <er> <medium>` | **Supported** |
| `hold` | — | No-op by definition |
| `redundancy_lost` | — | A report, not an action |
| `isolated` | — | A report, not an action |

### Experimento 003 — eco-resolução / eco-resolution

| Move | Simulator operation | Status |
|---|---|---|
| `Move(flow, "plte" \| "radio900")` | `failover` is **per site** | **Not expressible.** Eco assigns per **flow** |
| `Move(flow, "parked")` | — | **Not supported.** No operation stops one flow |

Isto não é uma lacuna de cobertura, é uma incompatibilidade de representação. `test_congestion_sheds_telemetry_before_scada` afirma que a telemetria de ER_03 vai para 900 MHz enquanto o SCADA do mesmo site permanece em LTE. A gramática do simulador não consegue exprimir um site com os dois fluxos em meios diferentes.

This is not a coverage gap but a representational mismatch. `test_congestion_sheds_telemetry_before_scada` asserts that ER_03's telemetry moves to 900 MHz while the same site's SCADA stays on LTE. The simulator's grammar cannot express a site with its two flows on different media.

## 3. Autoridade sobre o estado / State authority

O ns-3 é dono do estado da rede. Os experimentos 001–003 mantêm **crenças** derivadas de observações. Alterar um modelo Python não repara a rede.

ns-3 owns the network state. Experiments 001–003 hold **beliefs** derived from observations. Changing a Python model does not repair the network.

| Operation | Changes | Is it a repair? |
|---|---|---|
| `Topology.disable_link(a, b)` | the Python graph | **No.** A belief, or a what-if |
| `NetworkEcoWorld.apply(move)` | the eco world's assignment | **No.** A proposed allocation |
| STRIPS `delete=("node-stopped(?n)",)` | the planner's symbolic state | **No.** A prediction |
| `.scn` `failover` record | the plant's routing tables | **Yes.** The only one |

## 4. Conclusão medida, não simbólica / Measured completion

`verify_link` adiciona `link-up(?n)` assim que os literais `cleared-…` estão presentes. Isso é uma **previsão**, não uma confirmação. Um plano que termina em `service-restored(?n)` não afirma nada sobre a rede.

`verify_link` adds `link-up(?n)` as soon as the `cleared-…` literals hold. That is a **prediction**, not a confirmation. A plan ending in `service-restored(?n)` asserts nothing about the network.

A repetição causal já mostra a forma correta: janela de pontuação após a ação, prazo de resposta declarado, braço de controle idêntico, e recusa quando a telemetria pré-ação difere entre execuções. Falta generalizar isso para além de `switch_medium` — e, para as sete intervenções não suportadas, a conclusão correta hoje é **rejeitar**, não "pendente".

The causal replay already shows the right shape: a scoring window after the action, a declared reply deadline, an identical control arm, and refusal when pre-action telemetry differs between runs. What is missing is generalising it beyond `switch_medium` — and for the seven unsupported interventions, today's correct outcome is **reject**, not "pending".

## 5. Tempo e visibilidade / Timing and visibility

| Delay | Today | Missing |
|---|---|---|
| Fault onset | `fault_time_s = 10` | — |
| Observation window | `--probeStart` / `--probeStop` | no per-observation staleness |
| Decision | scripted `central_decision_delay_s = 3`; replay assumes 1 s | no measured controller latency |
| Execution | instantaneous route swap | no execution delay, no partial application |
| Action outcome | assumed to succeed | **no failed or delayed action is modelled** |

Nenhum componente hoje tolera uma ação que falha, chega tarde ou é aplicada pela metade.

No component today tolerates an action that fails, arrives late, or is half applied.

## 6. Controladores comparáveis ou cooperantes? / Comparable or cooperating controllers?

Hoje apenas o experimento 002 alcança a planta. 001 e 003 são demonstrações autônomas. A questão não é acadêmica: **eles já discordam.**

Today only experiment 002 reaches the plant. 001 and 003 are standalone demonstrations. The question is not academic: **they already disagree.**

No cenário `independent-faults`, para o site ER_03:

On the `independent-faults` scenario, for site ER_03:

| Component | Action | Evidence |
|---|---|---|
| 002 arbiter | switch the **whole site** to `radio900` | `test_congestion_is_not_traded_for_a_degraded_path` |
| 003 eco | move **only telemetry** to `radio900`; keep SCADA on `plte` | `test_congestion_sheds_telemetry_before_scada` |

Ambas são corretas sob as próprias regras. Executadas juntas, sem arbitragem declarada, produzem ações conflitantes sobre o mesmo site.

Both are correct under their own rules. Run together, with no declared arbitration, they produce conflicting actions on the same site.

Verificado executando os dois componentes sobre a mesma topologia e cenário: o árbitro devolve `switch_medium -> radio900`; a eco-resolução devolve `scada=plte`, `telemetry=radio900`. Não é a mesma ação, e o simulador só sabe exprimir a primeira.

Checked by running both components over the same topology and scenario: the arbiter returns `switch_medium -> radio900`; eco-resolution returns `scada=plte`, `telemetry=radio900`. Not the same action — and the simulator can express only the first.

## 7. Honestidade das abstrações / Abstraction honesty

**Contenção de MAC.** O rádio de 900 MHz é ponto a ponto: remotos sob o mesmo repetidor não disputam o meio. `mac_contention` não pode ser induzido nem avaliado. As regras S14, S15 e S25 existem, mas nada no simulador pode exercitá-las.

**MAC contention.** The 900 MHz radio is point-to-point: remote radios under the same relay do not contend for airtime. `mac_contention` can be neither induced nor evaluated. Rules S14, S15 and S25 exist, but nothing in the simulator can exercise them.

**Capacidade em fluxos contra largura de banda.** As capacidades da eco-resolução são contagens sem relação declarada com o modelo simulado:

**Flow-count capacity versus bandwidth.** Eco-resolution's capacities are counts with no declared relationship to the simulated model:

| Flow | Offered bit rate |
|---|---|
| SCADA (64 B + 256 B every 2 s) | 1 280 bps |
| Telemetry (512 B every 1 s) | 4 096 bps |
| One site, both flows | 5 376 bps |

| Eco capacity | Implied bit rate | Against the modelled link |
|---|---|---|
| SAF relay, 12 flows | 15 360 – 49 152 bps | **6 – 19.2 %** of the 256 kbps radio hop |
| eNodeB cell, 6 flows | 7 680 – 24 576 bps | negligible against a 5 MHz carrier |
| SAF congested, 3 flows | 3 840 – 12 288 bps | 1.5 – 4.8 % |
| Cell congested, 2 flows | 2 560 – 8 192 bps | negligible |

A eco-resolução declara um repetidor **cheio** com 12 fluxos enquanto o enlace simulado está ~80 % ocioso. E a falha de congestionamento do ns-3 é uma inundação UDP de 20 Mbps — cerca de **78×** o enlace de rádio inteiro. Os dois modelos de "congestionamento" compartilham o nome e nada mais.

Eco-resolution declares a relay **full** at 12 flows while the simulated link is ~80 % idle. And the ns-3 congestion fault is a 20 Mbps UDP flood — about **78×** the entire radio link. The two models of "congestion" share a name and nothing else.

## 8. O que construir antes de mais integração / What to build before more integration

1. **Rejeitar explicitamente ações não suportadas.** Um registro de ação que a planta não implementa deve levantar erro, como `FaultMechanism` já faz para mecanismos de falha. Hoje uma intervenção não suportada simplesmente não acontece, em silêncio. / **Explicitly reject unsupported actions.** An action the plant does not implement must raise, as `FaultMechanism` already does for fault mechanisms. Today an unsupported intervention silently does nothing.
2. **Ligar `rtt_ms` aos sujeitos de site.** Já medido; é o ganho mais barato da tabela. / **Wire `rtt_ms` to the site subjects.** Already measured; the cheapest win in the table.
3. **Substituir `verify_link` por uma verificação de telemetria.** / **Replace `verify_link` with a telemetry check.**
4. **Declarar o que cada agente eco observa e controla**, com alcance e atraso. / **Declare what each eco agent observes and controls**, with range and delay.
5. **Definir a relação fluxo ↔ bits**, ou declarar as capacidades como puramente ordinais. / **Define the flow ↔ bits relationship**, or declare the capacities as purely ordinal.
6. **Decidir se 001–003 são controladores alternativos ou cooperantes**, e tornar o conflito de ER_03 impossível ou explicitamente arbitrado. / **Decide whether 001–003 are alternative or cooperating controllers**, and make the ER_03 conflict either impossible or explicitly arbitrated.

## Enquadramento / Framing

O experimento 004 é o **ambiente de simulação compartilhado**. As demonstrações autônomas dos experimentos 001–003 e a repetição causal são **testes de componente**: valem para os seus próprios modelos, e as afirmações devem ser limitadas a isso até que as lacunas acima sejam fechadas.

Experiment 004 is the **shared simulation environment**. The standalone demonstrations of experiments 001–003, and the causal replay, are **component tests**: they hold for their own models, and claims should be limited accordingly until the gaps above are closed.
