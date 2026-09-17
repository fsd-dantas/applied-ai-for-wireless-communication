# 1 — Sistema especialista / Expert system

> Diagnostico de enlace degradado no cenario simulado, com regras de producao,
> encadeamento progressivo e regressivo, fatores de certeza e explicacao.
>
> Link-degradation diagnosis on the simulated scenario, with production rules,
> forward and backward chaining, certainty factors, and explanation.

Codigo / code: [`software/aisg/expert_system/`](../../software/aisg/expert_system/)

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/fsd-dantas/applied-ai-for-wireless-communication/main/docs/assets/figures/02-expert-system-dark.svg">
    <img src="https://raw.githubusercontent.com/fsd-dantas/applied-ai-for-wireless-communication/main/docs/assets/figures/02-expert-system-light.svg" alt="The 41 rules in five layers. Forward chaining rises from measurements to authorisation; backward chaining descends from the goal to the questions it needs." width="100%">
  </picture>
</p>

---

## Português

### Problema

Um enlace do backhaul simulado degradou ou caiu. **Por que?** E **o que fazer?**

O sistema classifica a causa entre oito hipoteses e recomenda uma acao, declarando quanta certeza tem em cada conclusao.

### Por que um sistema especialista, e nao inducao

Nao existe conjunto de dados rotulado de falhas **de campo** para este dominio. Para rotular um enlace real como *degradado* seria preciso um instrumento de degradacao controlada e uma linha de base de observabilidade autenticada. Sem os dois, o rotulo nao vem da medicao.

O cenario simulado inverte essa relacao: aqui o operador **comanda** a condicao, e portanto conhece o rotulo por construcao. O bloco `INDUCIBLE_BY` registra, para cada diagnostico, como induzi-lo. Por isso a base declara-se **rotulavel e repetivel** — e o teste `test_every_diagnosis_is_inducible_in_the_simulator` exige que nenhum diagnostico exista sem receita de inducao.

Ainda assim, codificar conhecimento em regras explicitas tem uma vantagem que nao e apenas de disponibilidade: a regra e **auditavel e contestavel**. Um especialista pode discordar da regra S14 e mudar so ela. Nao se discute assim com um peso de rede neural.

Essa e a razao pratica do contraste entre metodos **dedutivos** (regras dadas por especialistas) e **indutivos** (padroes extraidos de exemplos).

### Variaveis

**Evidencia observavel (13, perguntaveis):**

| Variavel | Tipo | Dominio |
|---|---|---|
| `rssi_dbm` | numerica | [-120, -30] dBm |
| `snr_db` | numerica | [-5, 40] dB |
| `excess_path_loss_db` | numerica | [0, 80] dB |
| `retry_rate_pct` | numerica | [0, 100] % |
| `packet_loss_pct` | numerica | [0, 100] % |
| `rtt_ms` | numerica | [0, 5000] ms |
| `offered_load_pct` | numerica | [0, 200] % |
| `node_responding` | booleana | yes, no |
| `upstream_relay_reachable` | booleana | yes, no |
| `route_present` | booleana | yes, no |
| `co_channel_emitter` | booleana | yes, no |
| `nodes_sharing_channel` | categorica | few, many |
| `neighbours_affected` | categorica | none, one, many |

A variavel discriminante e `retry_rate_pct`. Num meio compartilhado CSMA-CA, perda com sinal saudavel e **contencao**, e nao propagacao — e so essa grandeza separa as duas.

**Conclusoes intermediarias (2):** `signal_quality` (good, marginal, poor) e `link_symptom` (none, degraded, outage).

**Objetivos (3):** `diagnosis`, `recommended_action`, `authorization_required`.

**As oito hipoteses:** `rf_interference`, `excess_path_loss`, `mac_contention`, `node_failure`, `upstream_relay_failure`, `routing_misconfiguration`, `congestion`, `healthy`.

### As 41 regras, em cinco camadas

| Camada | Regras | Papel |
|---|---|---|
| 1 | S01–S04 | Medicoes de RF → `signal_quality` |
| 2 | S05–S08 | Estado do no e desempenho de fluxo → `link_symptom` |
| 3 | S10–S22 | Evidencia → `diagnosis` (oito hipoteses) |
| 3b | S23–S26 | **Contra-evidencia**: CF negativo contra hipoteses |
| 4 | S27–S34 | `diagnosis` → `recommended_action` |
| 5 | S35–S42 | `recommended_action` → `authorization_required` |

Sao 4 + 4 + 13 + 4 + 8 + 8 = **41 regras**. O identificador `S09` nao e usado: a numeracao tem um vao, a contagem nao.

A estratificacao importa: as regras da camada 3 nunca olham `rssi_dbm` diretamente, apenas `signal_quality`. Trocar o sensor de RF muda a camada 1 e nada mais.

**Um exemplo de cada tipo:**

```
S10:  SE emissor no mesmo canal = yes E qualidade do sinal = poor
      ENTAO diagnostico = rf_interference            (CF +0,85)

S25:  SE taxa de retransmissao MAC <= 30
      ENTAO diagnostico = mac_contention             (CF -0,80)   <- contra-evidencia

S35:  SE acao recomendada = change_channel
      ENTAO exige janela autorizada = yes            (CF +1,00)
```

### Fatores de certeza

Um fator de certeza (CF) esta em [-1, +1]: +1 confirmado, -1 refutado, 0 sem evidencia. Seguindo o MYCIN (Shortliffe e Buchanan, 1975):

- o CF de uma premissa e o **minimo** entre suas condicoes — o elo mais fraco;
- a regra contribui `CF_premissa x CF_regra`;
- a regra so dispara se a premissa passar do limiar 0,2, para que evidencia fraca nao se propague;
- duas conclusoes independentes sobre o mesmo fato combinam-se por:

```
ambos >= 0:   cf1 + cf2 * (1 - cf1)
ambos <= 0:   cf1 + cf2 * (1 + cf1)
sinais opostos: (cf1 + cf2) / (1 - min(|cf1|, |cf2|))
```

Evidencias que se reforcam aproximam-se de 1 sem nunca alcancar; evidencias contraditorias se cancelam. Duas evidencias de 0,8 dao 0,96 (`test_combine_cf_reinforcing_evidence_never_reaches_one`); +0,8 com -0,8 da exatamente 0; duas de -0,5 dao -0,75.

**A cadeia completa do caso `rf_interference`**, com os numeros que o programa imprime:

```
S10: premissa min(1,00 emissor; 0,90 qualidade) = 0,90  x  regra 0,85  =  0,765
S11: premissa min(1,00 emissor; 1,00 vizinhos)  = 1,00  x  regra 0,70  =  0,700
combinacao:  0,765 + 0,700 x (1 - 0,765)                               =  0,9295
S27: 0,9295 x 0,90                                                     =  0,8366
S35: 0,8366 x 1,00                                                     =  0,8366
```

Ou seja: diagnostico **+0,93**, acao recomendada **+0,84**, exigencia de janela **+0,84**. Nenhuma das duas evidencias sozinha chegaria la, e as duas juntas nao chegam a 1.

**Uma regra que dispara de novo nao conta a propria evidencia duas vezes.** A memoria de trabalho guarda a contribuicao de cada fonte separadamente e recombina; se uma regra dispara com premissa mais forte, ela **substitui** a propria contribuicao anterior (`test_a_rule_refiring_does_not_count_its_own_evidence_twice`).

### Contra-evidencia

Regras com CF negativo derrubam hipoteses concorrentes. No caso `congestion`, o quadro final de `diagnosis` e:

| Hipotese | CF | Regras |
|---|---|---|
| `congestion` | **+0,89** | S20+S21 |
| `excess_path_loss` | -0,85 | S23 |
| `mac_contention` | -0,80 | S25 |
| `rf_interference` | -0,70 | S24 |

Retransmissao baixa e evidencia **contra** contencao de MAC; ausencia de emissor co-canal, **contra** interferencia; perda de percurso nominal, **contra** perda excedente. Sem isso, hipoteses sem apoio ficariam simplesmente ausentes em vez de explicitamente refutadas (`test_counter_evidence_suppresses_a_competing_hypothesis`).

### Encadeamento progressivo e regressivo

**Progressivo (dirigido por dados).** Parte dos fatos e deriva tudo o que puder. E o modo *alarme de monitoramento*: chega telemetria, o sistema conclui.

O ciclo e reconhecer-agir: monta o conjunto de conflito, resolve o conflito e dispara **uma** regra por ciclo. Uma por ciclo, e nao todas, para que a ordem do raciocinio fique visivel no trace — e para que a resolucao de conflito tenha efeito observavel. Uma regra so volta a disparar se a premissa tiver **aumentado**, o que garante a terminacao (`test_forward_chaining_terminates_and_fires_each_rule_at_most_once`).

**Regressivo (dirigido por objetivo).** Parte da pergunta "o diagnostico e X?" e busca so a evidencia que a sustenta. E o modo *engenheiro as 2 da manha*.

Duas propriedades tornam a consulta curta:

1. **Curto-circuito.** Assim que uma condicao e falsa, a regra e abandonada e as condicoes restantes **nao sao perguntadas**.
2. **Corte por suficiencia.** Quando o objetivo atinge CF >= 0,9, o motor para de procurar mais apoio.

Na pratica, o caso `mac_contention` conclui (CF +0,94) perguntando **6 das 13** variaveis perguntaveis:

| Perguntadas (6) | Nao perguntadas (7) |
|---|---|
| `rssi_dbm`, `snr_db`, `excess_path_loss_db`, `retry_rate_pct`, `co_channel_emitter`, `nodes_sharing_channel` | `packet_loss_pct`, `rtt_ms`, `offered_load_pct`, `node_responding`, `upstream_relay_reachable`, `route_present`, `neighbours_affected` |

O progressivo, com os mesmos fatos, chega a mesma conclusao — verificado em todos os oito casos por `test_backward_chaining_matches_forward_chaining_on_the_same_evidence`, e a contagem de 6 em 13 por `test_backward_chaining_asks_only_what_the_goal_requires`.

### Resolucao de conflito

Quando varias regras estao prontas, qual dispara primeiro?

| Politica | Criterio |
|---|---|
| `first-match` | Ordem da base de regras |
| `specificity` | Regra mais especifica primeiro (mais condicoes) — **padrao** |
| `recency` | Regra que usa os fatos mais recentes |

Com regras monotonicas, a politica muda **a ordem do raciocinio, nao o ponto fixo**. No caso `rf_interference`:

| Politica | Ordem de disparo (inicio) | Diagnostico | Acao |
|---|---|---|---|
| `first-match` | S01, S06, S10, S11, S23, S26 ... | rf_interference +0,9295 | change_channel +0,8366 |
| `specificity` | S01, S06, S11, S10, S23, S26 ... | rf_interference +0,9295 | change_channel +0,8366 |
| `recency` | S11, S27, S35, S06, S26, S23 ... | rf_interference +0,9295 | change_channel +0,8366 |

As ordens diferem de verdade — o `recency` chega a acao (S27) e a autorizacao (S35) antes mesmo de terminar a camada de sintoma — e os tres CFs finais sao identicos ate a sexta casa. Os testes verificam as duas metades: `test_conflict_resolution_policies_produce_different_firing_orders` e `test_downstream_certainty_does_not_depend_on_the_conflict_policy`.

Trecho real de `aisg diagnose --case congestion --strategy recency --trace`:

```
  conflict set: S21 chosen by recency over S24, S07, S26, S25, S23, S04
* S21: premise CF +1.00 x rule CF +0.60 => diagnosis = congestion (CF +0.60)
  conflict set: S33 chosen by recency over S24, S07, S26, S25, S23, S04
* S33: premise CF +0.60 x rule CF +0.80 => recommended_action = reroute_traffic (CF +0.48)
  conflict set: S41 chosen by recency over S24, S07, S26, S25, S23, S04
* S41: premise CF +0.48 x rule CF +1.00 => authorization_required = yes (CF +0.48)
  conflict set: S24 chosen by recency over S07, S26, S25, S23, S04
* S24: premise CF +1.00 x rule CF -0.70 => diagnosis = rf_interference (CF -0.70)
```

### Explicacao

**`por que`** (durante a consulta): mostra a cadeia de regras que levou ate a pergunta. Digite `?` no modo interativo.

**`como`** (apos a conclusao): percorre recursivamente as regras que sustentam o fato ate chegar aos fatos informados pelo usuario. Saida real de `aisg diagnose --case rf_interference --explain`:

```
diagnostico = rf_interference (CF +0,93, S10+S11)
  <= S10: SE emissor no mesmo canal = yes E qualidade do sinal = poor
          ENTAO diagnostico = rf_interference (CF +0,85)
     Sinal degradado com emissor ativo no mesmo canal.
      emissor no mesmo canal = yes (CF +1,00, given) - fato inicial
      qualidade do sinal = poor (CF +0,90, S01)
        <= S01: SE potencia recebida < -95,0 E relacao sinal-ruido < 8,0
                ENTAO qualidade do sinal = poor (CF +0,90)
          potencia recebida = -97,0 dBm (CF +1,00, given) - fato inicial
          relacao sinal-ruido = 6,0 dB (CF +1,00, given) - fato inicial
  <= S11: SE emissor no mesmo canal = yes E vizinhos afetados = many
          ENTAO diagnostico = rf_interference (CF +0,70)
```

Toda conclusao desce ate fatos informados: `test_how_traces_a_conclusion_back_to_user_supplied_facts`.

### Calibracao e limite de validade

Todos os limiares numericos vivem em `SIM_THRESHOLDS`, em [`kb_simulated.py`](../../software/aisg/expert_system/kb_simulated.py). Sao **nominais e nao calibrados**. Quando existir linha de base medida, ajustam-se os valores; as regras nao mudam. E por isso que o bloco esta declarado num unico lugar.

O proprio programa imprime o limite de validade ao final de cada consulta: o resultado vale para o **modelo simulado**, nao para radio fisico — o MAC simulado nao e o MAC proprietario de um equipamento real.

**Limitacao declarada.** `INDUCIBLE_BY` traz receita de inducao para os oito diagnosticos, mas o exportador ns-3 do [experimento 004](../004-multi-rat-simulation/) sabe induzir cinco: `mac_contention` e `routing_misconfiguration` ainda nao tem mecanismo, e `rf_interference` e `excess_path_loss` compartilham o mesmo. Registrado em [`research/roadmap.md`](../../research/roadmap.md).

### Como executar

```bash
aisg diagnose --case rf_interference --trace --explain
aisg diagnose --case congestion --strategy recency --trace
aisg diagnose --case mac_contention --mode backward --goal diagnosis
aisg diagnose --interactive --mode backward --goal diagnosis
```

Casos disponiveis: `rf_interference`, `excess_path_loss`, `mac_contention`, `node_failure`, `upstream_relay_failure`, `routing_misconfiguration`, `congestion`, `healthy`.

No modo interativo: `?` mostra o **por que** da pergunta; resposta vazia significa *nao sei* e a variavel fica desconhecida; e uma certeza opcional pode acompanhar a resposta — `many 0.6`.

A evidencia tambem pode vir de fora: `--from-observation FILE` le um registro de observacao, `--from-prometheus URL --subject ID` consulta o que a instrumentacao conseguir responder, e `--save-observation FILE` grava o registro para reexecutar a consulta offline.

---

## English

### Problem

A link on the simulated backhaul degraded or failed. **Why?** And **what should be done?** The system classifies the cause among eight hypotheses and recommends an action, stating how certain it is.

### Why an expert system rather than induction

No labelled **field** fault dataset exists for this domain: labelling a real link *degraded* would need a controlled degradation instrument and an authenticated observability baseline. The simulated scenario inverts that: the operator *commands* the condition, so the label is known by construction. The `INDUCIBLE_BY` block records how each diagnosis is induced, and `test_every_diagnosis_is_inducible_in_the_simulator` refuses any diagnosis without a recipe.

Even so, encoding judgement as explicit rules buys something beyond availability: a rule is **auditable and contestable**. An expert can disagree with rule S14 and change that rule alone. You cannot argue that way with a neural network weight.

### Variables

Thirteen askable observations (PHY: `rssi_dbm`, `snr_db`, `excess_path_loss_db`; MAC: `retry_rate_pct`; flow: `packet_loss_pct`, `rtt_ms`, `offered_load_pct`; scenario state: `node_responding`, `upstream_relay_reachable`, `route_present`, `co_channel_emitter`, `nodes_sharing_channel`, `neighbours_affected`), two intermediate conclusions (`signal_quality`, `link_symptom`), and three goals (`diagnosis`, `recommended_action`, `authorization_required`). Full domains in the Portuguese table above.

`retry_rate_pct` is the discriminator: on a shared CSMA-CA medium, loss with a healthy signal is contention rather than propagation, and only that figure separates them.

### The 41 rules, in five layers

Layer 1 (S01–S04) maps RF measurements to `signal_quality`; layer 2 (S05–S08) maps node state and flow performance to `link_symptom`; layer 3 (S10–S22) maps evidence to `diagnosis`; S23–S26 supply **counter-evidence** with negative CFs; layer 4 (S27–S34) maps diagnosis to action; layer 5 (S35–S42) decides whether an authorised window is required. That is 4 + 4 + 13 + 4 + 8 + 8 = **41**; the id `S09` is unused, so the numbering has a gap but the count does not.

Stratification matters: layer-3 rules never read `rssi_dbm` directly, only `signal_quality`. Replacing the RF sensor changes layer 1 and nothing else.

### Certainty factors

A CF lies in [-1, +1]. Following MYCIN: a premise's CF is the **minimum** across its conditions; a rule contributes `premise_cf x rule_cf`; a rule fires only above the 0.2 threshold; and independent conclusions combine with the MYCIN combination function. Reinforcing evidence approaches 1 without reaching it — two 0.8 observations give 0.96, while +0.8 against -0.8 gives exactly 0.

The `rf_interference` case chains all the way through: S10 contributes 0.90 x 0.85 = 0.765, S11 contributes 1.00 x 0.70 = 0.700, which combine to 0.9295 (**CF +0.93**); the action rule S27 then yields 0.8366 (**+0.84**) and the authorisation gate S35 carries it through unchanged. A rule that fires again *replaces* its own earlier contribution rather than compounding with itself.

### Counter-evidence

On the `congestion` case the final picture is `congestion` at **+0.89** while `excess_path_loss` sits at -0.85, `mac_contention` at -0.80 and `rf_interference` at -0.70. Low retry is evidence *against* contention; no co-channel emitter, *against* interference; nominal path loss, *against* excess loss. Unsupported hypotheses are explicitly refuted rather than merely absent.

### Forward and backward chaining

**Forward** (data-driven) starts from facts and derives everything it can — the *monitoring alarm* mode. The recognise-act cycle fires **one** rule per cycle so the reasoning order is visible in the trace and conflict resolution has an observable effect; a rule re-fires only on a strengthened premise, which guarantees termination.

**Backward** (goal-driven) starts from "is the diagnosis X?" and seeks only the evidence that supports it — the *engineer at 2 a.m.* mode. Two properties keep the consultation short: **short-circuiting** (once a condition is false, the rule is abandoned and the remaining conditions are never asked) and a **sufficiency cut-off** (once the goal reaches CF >= 0.9, the engine stops seeking further support). The `mac_contention` case concludes at CF +0.94 after asking 6 of the 13 askable variables — see the table above for which six — and reaches the same conclusion forward chaining does, on all eight cases.

### Conflict resolution

`first-match` (base order), `specificity` (most conditions first, the default), and `recency` (newest facts first). With monotonic rules, the policy changes **the order of reasoning, not the fixed point**: on `rf_interference` all three reach `rf_interference` at +0.9295 and `change_channel` at +0.8366 through visibly different firing orders — `recency` reaches the action and authorisation rules before finishing the symptom layer. The tests verify both halves of that claim.

### Explanation

**`why`** during the consultation shows the rule chain that led to the question (type `?`). **`how`** after the conclusion walks the supporting rules recursively down to user-supplied facts — see the rendered example in the Portuguese section.

### Calibration and validity limit

Every numeric threshold lives in `SIM_THRESHOLDS`. They are **nominal and uncalibrated**; when a measured baseline exists the values are re-fitted and the rules stay as they are. The program prints its validity limit after every consultation: results hold for the simulated model, not for physical radio.

**Declared limitation.** `INDUCIBLE_BY` carries an induction recipe for all eight diagnoses, but the experiment 004 exporter can induce five: `mac_contention` and `routing_misconfiguration` have no mechanism yet, and `rf_interference` and `excess_path_loss` share one. Tracked in [`research/roadmap.md`](../../research/roadmap.md).
