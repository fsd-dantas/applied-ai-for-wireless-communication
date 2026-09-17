[Applied AI for Wireless Communication](../../README.md) › [experiments](../../docs/experiment-catalogue.md) › **004 Multi-RAT simulation**

# 004 — Simulação multi-RAT em ns-3 / Multi-RAT ns-3 simulation

> **PT-BR** — O backhaul em duplo acesso da topologia declarada — cadeia de repetidores armazena-e-encaminha em 900 MHz e LTE privativo alcançando os mesmos roteadores de borda — construído num simulador de eventos discretos, para que as recomendações dos experimentos anteriores possam ser verificadas contra tráfego simulado.
>
> **EN** — The dual-homed backhaul from the declared topology — a 900 MHz store-and-forward relay chain and private LTE reaching the same edge routers — built in a discrete-event simulator, so the recommendations of the earlier experiments can be checked against simulated traffic.

Questão / Question: [RQ6](../../research/research-questions.md) · Programa / program: [`software/ns-3-modules/`](../../software/ns-3-modules/) · Exportador / exporter: [`software/aisg/simulation/`](../../software/aisg/simulation/) · Estado / Status: **concluído no modelo / complete on the model**

---

## Objetivo / Objective

Construir o backhaul em duplo acesso da topologia declarada num simulador de eventos discretos (ns-3), para que as recomendações dos experimentos 001–003 — diagnóstico, plano de restauração e decisão de troca de meio — possam ser verificadas contra tráfego simulado, e não apenas contra um conjunto esperado escrito à mão.

Build the dual-homed backhaul from the declared topology in a discrete-event simulator (ns-3), so the recommendations of experiments 001–003 — diagnosis, restoration plan and medium-switch decision — can be checked against simulated traffic, rather than only against a hand-written expected set.

## Questão de pesquisa / Research question

> **RQ6 — Verificação por simulação.** As recomendações, aplicadas a uma rede multi-RAT simulada, restauram o serviço que prometem?
>
> **RQ6 — Simulation-grounded verification.** Do the recommendations, applied to a simulated multi-RAT network, restore the service they promise?

Ver [`research/research-questions.md`](../../research/research-questions.md) para as demais subquestões (RQ1–RQ6).
See [`research/research-questions.md`](../../research/research-questions.md) for the other sub-questions (RQ1–RQ6).

## Hipótese / Hypothesis

Os incidentes diagnosticados pelo quadro-negro ([experimento 002](../002-multi-expert-blackboard/)) e seu plano central de troca de meio, aplicados a tráfego simulado no backhaul em ns-3, restauram o serviço exatamente nos sites que o modelo prevê, e o fazem mais rápido do que um failover puramente local que reage a consultas perdidas. Um plano baseado numa regra de arbitragem errada produz perda mensuravelmente maior do que um plano corrigido — o que a própria simulação deve ser capaz de expor.

The incidents the blackboard ([experiment 002](../002-multi-expert-blackboard/)) diagnoses, and its central medium-switch plan, applied to simulated traffic on the ns-3 backhaul, restore service at exactly the sites the model predicts, and do so faster than a purely local failover reacting to missed polls. A plan based on a wrong arbitration rule produces measurably higher loss than a corrected one — which the simulation itself must be able to expose.

Falseabilidade: um site previsto como restaurado que permaneça com perda, ou um site previsto como afetado que não perca serviço, refuta a hipótese central; o achado 4 em [Resultados](#resultados--results) é a própria hipótese de exposição de regra errada, confirmada.

Falsifiability: a site predicted as restored that keeps losing service, or a site predicted as affected that loses none, refutes the central hypothesis; finding 4 in [Results](#resultados--results) is the wrong-rule-exposure hypothesis itself, confirmed.

## Tópicos relacionados / Related topics

- [RQ6](../../research/research-questions.md) — questão respondida por este experimento / the question this experiment answers.
- [Experimento 002](../002-multi-expert-blackboard/) — os cenários de falha e o plano central sob teste; a regra de manutenção do árbitro foi corrigida a partir daqui / the fault scenarios and the central plan under test; the arbiter's hold rule was corrected from here.
- [Experimento 003](../003-eco-resolution/) — explica por que o failover local oscila (achado 3) / explains why local failover flaps (finding 3).
- [`software/ns-3-modules/README.md`](../../software/ns-3-modules/README.md) — guia de instalação do zero e execução / from-scratch setup and run guide.

## Modelo do sistema / System model

| Elemento / Element | ns-3 | Parâmetros / Parameters |
|---|---|---|
| Fibra / Fibre | `PointToPoint` | taxa nominal; atraso = distância / 2·10⁸ m/s / nominal rate; delay = distance / 2·10⁸ m/s |
| Rádio 900 MHz armazena-e-encaminha / 900 MHz store-and-forward radio | `PointToPoint` + `DropTailQueue` + `RateErrorModel` | taxa nominal; atraso = propagação + sobrecarga do modelo de custo; PER do orçamento de enlace / nominal rate; delay = propagation + cost-model overhead; PER from the link budget |
| Cabo até o roteador de borda / Cable to the edge router | `PointToPoint` | 100 Mbps |
| LTE privativo / Private LTE | `LteHelper` + `PointToPointEpcHelper`, Okumura-Hata | banda 31 (465 MHz DL), 5 MHz / band 31 (465 MHz DL), 5 MHz |
| Antena do CPE / CPE antenna | `CosineAntennaModel` apontada para o eNodeB servidor / aimed at the serving eNodeB | 12 dBi, 65°; `--cpeGain` sobrepõe o ganho / overrides the gain |
| Repetidores LTE / LTE relays | modelados como eNodeBs / modelled as eNodeBs | o ns-3 não implementa repetidores LTE / ns-3 implements no LTE relays |
| Roteador atrás do CPE / Router behind the CPE | túnel UDP NOC ↔ CPE (`VirtualNetDevice`) / NOC ↔ CPE UDP tunnel | o PGW só entrega tráfego a endereços de UE / the PGW only delivers to UE addresses |
| Tráfego / Traffic | sockets UDP / UDP sockets | SCADA pedido/resposta a partir do NOC; telemetria periódica do site / SCADA request/response from the NOC; periodic site telemetry |

Endereços de serviço sintéticos / synthetic service addresses: NOC `10.255.0.1`, site *k* `172.16.k.1`.

**Decisões de modelagem / Modelling decisions:**

- **Repetidores LTE viram eNodeBs.** O ns-3 não implementa repetidores LTE. / **LTE relays become eNodeBs.** ns-3 implements no LTE relays.
- **Roteador atrás do CPE por túnel.** O PGW só entrega tráfego a endereços de UE; um túnel UDP NOC ↔ CPE leva o tráfego até o site. / **Router behind the CPE through a tunnel.** The PGW only delivers to UE addresses; a NOC ↔ CPE UDP tunnel carries traffic to the site.
- **CPE com antena diretiva.** Um CPE fixo externo usa antena diretiva apontada para o eNodeB (12 dBi, 65°, nominal). Com CPE isotrópico de 23 dBm, o uplink dos sites mais distantes não fecha: ER_11, ER_12 e ER_15 perdiam todo o tráfego de subida. / **Directional CPE antenna.** A fixed outdoor CPE uses a directional antenna aimed at its eNodeB (12 dBi, 65°, nominal). With an isotropic 23 dBm CPE, the uplink of the farthest sites does not close: ER_11, ER_12 and ER_15 lost all uplink traffic.
- **Rádio 900 MHz abstrato e declarado.** Não há modelo do rádio proprietário; cada salto é ponto a ponto com taxa, atraso e erro de pacote nominais. / **Abstract, declared 900 MHz radio.** No model of the proprietary radio exists; every hop is point-to-point with nominal rate, delay and packet error.
- **Meio primário = rota nominal de menor custo.** A rota pela malha de 900 MHz fica sempre instalada; o failover só muda as extremidades. / **Primary medium = nominal least-cost route.** The 900 MHz route is always installed; failover only changes the ends.

O programa é um projeto CMake independente, ligado a um ns-3 instalado como biblioteca — não vive dentro de `scratch/`. Ver [`software/ns-3-modules/README.md`](../../software/ns-3-modules/README.md).

The program is a standalone CMake project, linked against an ns-3 installed as a library — it does not live inside `scratch/`. See [`software/ns-3-modules/README.md`](../../software/ns-3-modules/README.md).

## Cenário e premissas / Scenario and assumptions

| Item | Valor / Value |
|---|---|
| Nós / Nodes | 60 (NOC, 7 eNodeBs, 15 CPEs, 7 repetidores SAF / SAF relays, 15 rádios remotos / remote radios, 15 roteadores de borda / edge routers) |
| Enlaces ponto a ponto / Point-to-point links | 52 (fibra / fibre, rádio 900 MHz, cabo / cable) |
| Sites | 15, cada um cabeado a um rádio remoto e a um CPE / each wired to one remote radio and one CPE |
| LTE | banda 31, 5 MHz, Okumura-Hata / band 31, 5 MHz, Okumura-Hata |
| Tráfego / Traffic | SCADA pedido/resposta a cada 2 s; telemetria de 512 B a cada 1 s / SCADA request/response every 2 s; 512 B telemetry every 1 s |

A topologia é a mesma `dual` (60 nós) dos experimentos 002 e 003 — a única fonte de verdade; o arquivo de cenário `.scn` é derivado dela e reprodutível. / The topology is the same `dual` (60 nodes) as experiments 002 and 003 — the single source of truth; the `.scn` scenario file is derived from it and reproducible.

As falhas são as comandadas nos cenários do [experimento 002](../002-multi-expert-blackboard/); o plano central é a decisão de troca de meio do próprio quadro-negro, aplicada 3 s após a falha. / The faults are those commanded by the [experiment 002](../002-multi-expert-blackboard/) scenarios; the central plan is the blackboard's own medium-switch decision, applied 3 s after the fault.

Topologia sintética; resultados valem para o modelo — ver [Limitações](#limitações--limitations).
Synthetic topology; results hold for the model — see [Limitations](#limitações--limitations).

## Software e versões / Software and versions

ns-3.48, compilado em C++23 com GCC 13+ (Ubuntu 24.04 / WSL2), instalado como biblioteca (`./ns3 install`) e consumido por `find_package(ns3)`. Patch de banda 31 aplicado à árvore do ns-3 ([`patches/lte-band-31.patch`](../../software/ns-3-modules/patches/lte-band-31.patch)). Exportador em Python 3.10+ (pacote `aisg`, versão 0.11.0, sem dependências de terceiros no núcleo).

ns-3.48, built as C++23 with GCC 13+ (Ubuntu 24.04 / WSL2), installed as a library (`./ns3 install`) and consumed via `find_package(ns3)`. Band 31 patch applied to the ns-3 tree ([`patches/lte-band-31.patch`](../../software/ns-3-modules/patches/lte-band-31.patch)). Python 3.10+ exporter (`aisg` package, version 0.11.0, no third-party dependencies in the core).

Guia completo de instalação do zero / full from-scratch setup guide: [`software/ns-3-modules/README.md`](../../software/ns-3-modules/README.md).

## Configuração / Configuration

`aisg ns3-export` gera o arquivo `.scn` a partir da topologia declarada, com ou sem um cenário de falha do experimento 002 embutido:

`aisg ns3-export` generates the `.scn` file from the declared topology, with or without one of experiment 002's fault scenarios embedded:

```bash
aisg ns3-export --out experiments/004-multi-rat-simulation/configuration/dual-homed-60.scn
aisg ns3-export --fault-scenario saf-chain-outage \
  --out experiments/004-multi-rat-simulation/configuration/dual-homed-60-saf-chain-outage.scn
```

| Modo de failover / Failover mode | Comportamento / Behaviour |
|---|---|
| `none` | rotas estáticas nominais / nominal static routes |
| `local` | o NOC troca o downlink após 3 respostas perdidas; o roteador de borda troca o uplink após 3 intervalos sem consulta / the NOC switches the downlink after 3 missed replies; the edge router switches the uplink after 3 intervals without a poll |
| `central` | ambas as extremidades trocam conforme o plano do quadro-negro, aplicado 3 s após a falha / both ends switch as the blackboard plans, applied 3 s after the fault |

## Dados de entrada / Input data

Os quatro arquivos `.scn` em [`configuration/`](configuration/), todos derivados da mesma topologia `dual`: o cenário base sem falha (`dual-homed-60.scn`) e os três cenários de falha do experimento 002 (`dual-homed-60-saf-chain-outage.scn`, `dual-homed-60-dual-outage.scn`, `dual-homed-60-independent-faults.scn`).

The four `.scn` files in [`configuration/`](configuration/), all derived from the same `dual` topology: the fault-free base scenario (`dual-homed-60.scn`) and experiment 002's three fault scenarios (`dual-homed-60-saf-chain-outage.scn`, `dual-homed-60-dual-outage.scn`, `dual-homed-60-independent-faults.scn`).

## Procedimento de execução / Execution procedure

Instalação do ns-3 e compilação do programa / installing ns-3 and building the program: [`software/ns-3-modules/README.md`](../../software/ns-3-modules/README.md).

```bash
# na raiz do repositório / from the repository root
aisg ns3-export --fault-scenario saf-chain-outage --out experiments/004-multi-rat-simulation/configuration/dual-homed-60-saf-chain-outage.scn
software/ns-3-modules/dual-homed-backhaul/build/dual-homed-backhaul \
  --scenario=experiments/004-multi-rat-simulation/configuration/dual-homed-60-saf-chain-outage.scn \
  --outDir=/tmp/saf-chain-outage-none --failover=none   # none | local | central
```

## Métricas / Metrics

| Arquivo / File | Métrica / Metric |
|---|---|
| `sites.csv` | meio primário, pedidos SCADA enviados/recebidos, perda (%), RTT médio e máximo, telemetria enviada/recebida / primary medium, SCADA requests sent/received, loss (%), mean and max RTT, telemetry sent/received |
| `requests.csv` | RTT por consulta SCADA individual / RTT per individual SCADA poll |
| `events.csv` | instante e motivo de cada falha injetada e troca de meio / time and reason of every injected fault and medium switch |
| `flowmon.xml` | estatísticas de FlowMonitor por fluxo / per-flow FlowMonitor statistics |

Perda é definida como consultas SCADA enviadas na janela de medição (16–29 s) sem resposta em 2 s; sete consultas por site nessa janela, logo uma consulta perdida vale 14,3%. / Loss is defined as SCADA polls sent in the measurement window (16–29 s) with no reply within 2 s; seven polls per site in that window, so one lost poll is 14.3%.

## Resultados / Results

Falha aos 10 s. Arquivos em [`results/`](results/). / Fault at 10 s. Files under [`results/`](results/).

| Cenário / Scenario | Sem failover / No failover | Local | Central (plano do quadro-negro / blackboard plan) |
|---|---|---|---|
| SAF_02 parado / down | ER_06: 100% | ER_06: 0% (troca aos / switch at 16,0 s) | ER_06: 0% (troca aos / switch at 13,0 s) |
| SAF_02 + RELAY_5 parados / down | ER_03, ER_04, ER_06, ER_07: 100% | 100%, **20 trocas / switches** | 100%, nenhuma troca / no switch |
| Interferência RM_07 + congestionamento RELAY_5 / Interference RM_07 + congestion RELAY_5 | ER_04, ER_07: 14,3% | 14,3%, nenhuma troca / no switch | ER_03, ER_04: 0%; ER_07: 14,3% (mantido / held) |

### Achados / Findings

1. **O simulador reproduz as previsões do quadro-negro**: o site afetado pela queda de SAF_02 e exatamente os quatro sites isolados na queda dupla. / **The simulator reproduces the blackboard's predictions**: the site affected by SAF_02 and exactly the four sites isolated by the dual outage.
2. **O failover central é mais rápido quando o plano é correto**: 3 s de decisão contra a detecção de 3 consultas perdidas. / **Central failover is faster when the plan is right**: 3 s to decide against detecting 3 missed polls.
3. **O failover local oscila quando os dois meios caem e não reage a perda parcial.** É mantido como resultado, e não corrigido com temporizador: é o problema de coordenação que o experimento 003 (eco-resolução) trata. / **Local failover flaps when both media are down and does not react to partial loss.** It is kept as a result, not patched with a timer: it is the coordination problem experiment 003 (eco-resolution) addresses.
4. **A verificação corrigiu o quadro-negro.** Na primeira versão, o árbitro trocou ER_07 do LTE congestionado para o rádio interferido de RM_07, e a perda subiu de 14,3% para 57,1% (commit `f88db83`). O árbitro ganhou a regra de manutenção; na nova execução, ER_07 permanece em 14,3%. / **Verification corrected the blackboard.** In the first version, the arbiter moved ER_07 off congested LTE onto RM_07's interfered radio, and loss rose from 14.3% to 57.1% (commit `f88db83`). The arbiter gained the hold rule; in the new run, ER_07 stays at 14.3%.

## Limitações / Limitations

- Uma execução determinística por caso; sem sementes múltiplas nem intervalos de confiança. / One deterministic run per case; no multiple seeds or confidence intervals.
- Sete consultas por site na janela de medição: uma consulta perdida vale 14,3%. / Seven polls per site in the measurement window: one lost poll is 14.3%.
- Congestionamento modelado como inundação UDP de 20 Mbps por CPE; interferência como taxa de erro de pacote de 0,6 nos enlaces de RM_07. / Congestion modelled as a 20 Mbps UDP flood per CPE; interference as a 0.6 packet error rate on RM_07's links.
- O ciclo diagnóstico → plano → verificação ainda não fecha: a telemetria simulada ainda não é exportada de volta como registro de observação para o quadro-negro. / The diagnosis → plan → verification loop does not close yet: simulated telemetry is not yet exported back as an observation record for the blackboard.

## Estado de reprodutibilidade / Reproducibility status

**Reproduzível a partir dos arquivos versionados.** Cada execução é determinística para uma dada semente e arquivo `.scn`; os resultados em [`results/`](results/) foram gerados pelo programa quando ainda vivia em `scratch/`. A migração para um projeto CMake independente (ver [Modelo do sistema](#modelo-do-sistema--system-model)) **teve sua saída confirmada como idêntica** à dos resultados versionados em 2026-09-17: o cenário `saf-chain-outage` com `--failover=central` reproduziu `sites.csv`, `requests.csv` e `events.csv` byte a byte, inclusive com `--animate` ativo. O passo 7 do guia de instalação em [`software/ns-3-modules/README.md`](../../software/ns-3-modules/README.md) é exatamente essa checagem. Os outros oito diretórios de resultados ainda não foram conferidos um a um.

**Reproducible from the versioned files.** Each run is deterministic for a given seed and `.scn` file; the results under [`results/`](results/) were generated by the program while it still lived in `scratch/`. The migration to a standalone CMake project (see [System model](#modelo-do-sistema--system-model)) **has had its output confirmed identical** to the versioned results, on 2026-09-17: the `saf-chain-outage` scenario with `--failover=central` reproduced `sites.csv`, `requests.csv` and `events.csv` byte for byte, with `--animate` enabled. Step 7 of the setup guide in [`software/ns-3-modules/README.md`](../../software/ns-3-modules/README.md) is exactly that check. The other eight result directories have not yet been checked one by one.

Execuções mais longas com várias sementes ainda não existem — ver [Limitações](#limitações--limitations).
Longer runs with multiple seeds do not exist yet — see [Limitations](#limitações--limitations).

## Próximas etapas / Next steps

Exportar a telemetria simulada como registros de observação para o quadro-negro, fechando o ciclo diagnóstico → plano → verificação; execuções mais longas com várias sementes. / Export simulated telemetry as observation records for the blackboard, closing the diagnosis → plan → verification loop; longer runs with several seeds.

## Material de manuscrito relacionado / Related manuscript material

Este README é copiado como `EXPERIMENT.md` no pacote ns-3 de cada release (ver [`.github/workflows/release.yml`](../../.github/workflows/release.yml)). / This README is copied as `EXPERIMENT.md` into the ns-3 bundle of every release (see [`.github/workflows/release.yml`](../../.github/workflows/release.yml)).

`manuscripts/presentations/` — deck, roteiro de fala e notebook: locais, não publicados neste repositório; a wiki é a companhia pública. / deck, speaking script and notebook: local, not published in this repository; the wiki is the public companion.
