# 2 — Geracao automatica de planos / Automated plan generation

> Representacao STRIPS, solucionador GPS por analise meios-fins e planejador
> progressivo por A*.
>
> STRIPS representation, GPS means-ends solver, and A* progression planner.

Codigo / code: [`software/aisg/planning/`](../../software/aisg/planning/)

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/fsd-dantas/applied-ai-for-wireless-communication/main/docs/assets/figures/03-planning-dark.svg">
    <img src="https://raw.githubusercontent.com/fsd-dantas/applied-ai-for-wireless-communication/main/docs/assets/figures/03-planning-light.svg" alt="On the left, the three sets that define a STRIPS action. On the right, the GPS means-ends recursion for restoring service on a node." width="100%">
  </picture>
</p>

Como o dominio foi decidido e por que ele e valido: [`planner-design-process.md`](planner-design-process.md).
How the domain was decided and why it is valid: [`planner-design-process.md`](planner-design-process.md).

---

## Português

### Problema

O sistema especialista diagnosticou uma falha e recomendou uma acao. **Em que sequencia executa-la?** Nada pode alterar o cenario antes da autorizacao, e alterar um parametro do cenario exige interromper a execucao em curso.

Objetivo: `service-restored(N)` e `logged(N)`.

### STRIPS: a representacao

STRIPS (Fikes e Nilsson, 1971) representa uma acao por tres conjuntos:

- **precondicoes** — o que precisa ser verdade para aplicar;
- **lista de adicao** — o que passa a ser verdade;
- **lista de remocao** — o que deixa de ser verdade.

O estado do mundo e o conjunto de literais positivos verdadeiros. O que nao esta no conjunto e falso: **hipotese do mundo fechado**.

```
separate_channels(?n)
  precondicoes:  authorized(?n), mac-contention(?n), run-stopped(?n)
  adiciona:      cleared-mac-contention(?n)
  remove:        mac-contention(?n)
  custo:         3
```

### Os treze operadores

| Operador | Custo | Exige autorizacao? | Exige execucao parada? |
|---|---|---|---|
| `request_authorization(?n)` | 1 | — | nao |
| `change_channel(?n)` | 2 | sim | nao |
| `restore_relay(?n)` | 2 | sim | nao |
| `restart_node(?n)` | 1 | sim | nao |
| `fix_routing(?n)` | 1 | sim | nao |
| `reroute_traffic(?n)` | 2 | sim + rota alternativa | nao |
| `stop_run(?n)` | 2 | sim | — (exige execucao ativa) |
| `start_run(?n)` | 2 | — | exige execucao parada |
| `restore_path_budget(?n)` | 1 | sim | **sim** |
| `separate_channels(?n)` | 3 | sim | **sim** |
| `verify_link(?n)` | 1 | — | exige execucao **ativa** |
| `record_logbook(?n)` | 1 | — | — |
| `close_work_order(?n)` | 1 | — | — |

### Governanca como precondicao, nao como recomendacao

Todo operador que altera o cenario exige `authorized(?n)` — diretamente, ou, no caso de `start_run`, atraves do `stop_run` que precisa precede-lo. Isso torna "agimos sem autorizacao" um estado **inalcancavel** em vez de uma verificacao em tempo de execucao — uma tecnica de modelagem STRIPS. Apenas verificar, registrar e encerrar escapam da exigencia, porque nao alteram nada.

O teste `test_no_scenario_changing_action_precedes_authorisation` verifica a invariante em todos os diagnosticos, e `test_every_plan_records_the_logbook_before_closing` verifica que a ordem de servico nunca fecha antes do registro.

### Um literal `cleared-<falha>` por falha

`verify_link` exige `cleared-<falha>(?n)` para **cada** falha diagnosticada no problema, e nao um sinalizador unico compartilhado. Com um sinalizador unico, corrigir uma falha entre varias liberava a verificacao e o plano fechava a ordem de servico com o defeito ainda presente — e `Plan.validate` retornava verdadeiro, porque o objetivo realmente estava satisfeito.

Dois testes guardam a correcao: `test_a_plan_never_closes_the_work_order_with_a_fault_still_present` e `test_verification_is_blocked_until_every_fault_is_cleared`. A historia completa do defeito esta em [`planner-design-process.md`](planner-design-process.md), secao 6.

### O que custa aqui e parar a execucao

Se todas as acoes custassem 1, planejar seria contar passos. O que da peso ao planejamento neste dominio nao e deslocamento de equipe — e o **custo de invalidar a execucao em curso**.

Alterar um **parametro do cenario** (o orcamento de percurso, o plano de canais) nao pode ser absorvido pela execucao em andamento: e preciso parar e retomar, ao custo de 2 + 2 = **4**. Um reparo **em tempo de execucao** (reativar um no, mudar de canal, corrigir uma rota) nao paga nada disso.

A consequencia e o compromisso que torna o planejamento necessario: **agrupar as correcoes de parametro numa unica parada**. O planejador de fato agrupa.

```
uma falha de parametro (mac-contention)          custo 11
 1. request_authorization   [1]     5. verify_link        [1]
 2. stop_run                [2]     6. record_logbook     [1]
 3. separate_channels       [3]     7. close_work_order   [1]
 4. start_run               [2]

duas falhas de parametro (mac-contention + excess-path-loss)   custo 12
 1. request_authorization   [1]     5. start_run          [2]
 2. stop_run                [2]     6. verify_link        [1]
 3. restore_path_budget     [1]     7. record_logbook     [1]
 4. separate_channels       [3]     8. close_work_order   [1]
```

A segunda correcao custa **+1**, e nao +5: ela entra na parada que ja foi paga. Verificado em `test_parameter_changes_share_one_run_restart` (exatamente um `stop_run` e um `start_run`).

O contraste completa o argumento: com apenas `node-stopped`, o plano tem 5 acoes e custo 5, **sem nenhuma parada** — `test_a_runtime_repair_needs_no_run_restart`. E parar nao e uma precaucao gratuita: `verify_link` exige `run-active(?n)`, entao a execucao precisa ser retomada antes da verificacao (`test_verification_requires_the_run_active_again`).

### GPS: analise meios-fins

O GPS de Newell e Simon (1961) planeja por **analise meios-fins**:

1. olhe a **diferenca** entre o estado atual e o objetivo;
2. escolha um operador que **reduza** essa diferenca (a lista de adicao contem o objetivo);
3. **recursivamente**, satisfaca as precondicoes desse operador;
4. aplique o operador.

O 'porque' de cada acao e explicito: toda acao existe para eliminar uma diferenca concreta. E por isso que o trace do GPS se le como uma justificativa, e nao como um log de busca. Trecho real de `aisg plan --diagnosis mac_contention --node SAF_02 --solver gps --trace`:

```
OBJETIVO: logged(SAF_02), service-restored(SAF_02)
DIFERENCA a reduzir: logged(SAF_02)
  operador candidato: record_logbook(SAF_02)
  precondicoes de record_logbook(SAF_02): link-up(SAF_02)
    DIFERENCA a reduzir: link-up(SAF_02)
      operador candidato: verify_link(SAF_02)
      precondicoes: cleared-mac-contention(SAF_02), diagnosed(SAF_02), run-active(SAF_02)
        DIFERENCA a reduzir: cleared-mac-contention(SAF_02)
          operador candidato: separate_channels(SAF_02)
          precondicoes: authorized(SAF_02), mac-contention(SAF_02), run-stopped(SAF_02)
            DIFERENCA a reduzir: authorized(SAF_02)
              APLICA request_authorization(SAF_02)  =>  authorized(SAF_02)
            ja satisfeito: mac-contention(SAF_02)
            DIFERENCA a reduzir: run-stopped(SAF_02)
              APLICA stop_run(SAF_02)  =>  run-stopped(SAF_02)
          APLICA separate_channels(SAF_02)  =>  cleared-mac-contention(SAF_02)
        ...
  APLICA close_work_order(SAF_02)  =>  service-restored(SAF_02)
```

O plano e a pilha desenrolada na ordem inversa.

### Limitacoes do GPS, ditas com todas as letras

**O GPS nao e completo nem otimo.** Ele adota o primeiro operador que reduz a diferenca e so revisa por retrocesso em caso de falha.

Ele tambem sofre da **anomalia de Sussman**: com subobjetivos que interagem, atingi-los um a um pode desfazer trabalho ja feito. A implementacao adota a defesa minima: apos satisfazer todos os subobjetivos, reverifica se algum foi desfeito e, se foi, **falha explicitamente** em vez de devolver um plano invalido.

**Um caso concreto de nao-otimalidade**, verificado em `test_gps_can_be_suboptimal_when_a_cheap_action_has_expensive_preconditions`: o GPS ordena os operadores relevantes pelo custo **proprio**, sem olhar o custo das **precondicoes**. Se a acao barata (custo 1) exigir um deslocamento caro (custo 10) e existir uma correcao remota de custo 3, o GPS escolhe o plano de custo 11; o A* encontra o de custo 3.

**Mas esse problema e construido, e nao este dominio.** Aqui o GPS **nunca perde em custo** para o A*: `test_gps_matches_a_star_on_every_solvable_fault_combination` compara as **63 combinacoes** de ate tres falhas e encontra o mesmo custo em todas. A razao e estrutural, e o grafo de planejamento a nomeia: **nenhum literal deste dominio tem mais de um operador que o produza**, entao a analise meios-fins nao tem escolha para errar.

Custo igual nao quer dizer plano identico: com `node-stopped` e `mac-contention` juntos, os dois solucionadores devolvem custo 12 ordenando de forma diferente os reparos independentes.

E exatamente por isso que os dois planejadores convivem neste repositorio: um mostra o raciocinio, o outro garante o custo.

### Planejador progressivo por A*

O planejamento vira busca:

| Busca | Planejamento |
|---|---|
| estado | conjunto de literais verdadeiros |
| sucessor | qualquer acao aplicavel |
| custo do passo | custo da acao |
| teste de objetivo | o objetivo esta contido no estado |

Com isso, **a mesma funcao `astar`** do terceiro trabalho resolve o planejamento. Nao e uma copia adaptada: e a mesma funcao, importada de [`aisg.search.algorithms`](../../software/aisg/search/algorithms.py).

**Heuristica `goal_count`:** h(s) = numero de literais do objetivo ainda nao satisfeitos — no maximo 2, porque o objetivo tem dois literais.

Ela e admissivel **apenas se** nenhuma acao satisfizer mais de um literal do objetivo e toda acao custar ao menos 1. Neste dominio a condicao vale: `service-restored` e `logged` sao adicionados por operadores diferentes, cada um de custo unitario. Declaramos a condicao em vez de supo-la — uma heuristica inadmissivel custaria a otimalidade em silencio.

A heuristica `zero` reduz o A* a busca de custo uniforme e serve de condicao de controle; `test_goal_count_heuristic_does_not_change_the_optimal_plan_cost` confirma que as duas chegam ao mesmo custo.

Esforco de busca sobre o cenario `dual`, no `SAF_02`:

| Diagnostico | Acoes | Custo | Expandidos | Gerados | Pico |
|---|---|---|---|---|---|
| `mac_contention` | 7 | 11 | 8 | 21 | 3 |
| `congestion` | 5 | 6 | 7 | 20 | 4 |
| `rf_interference` | 5 | 6 | 7 | 20 | 4 |
| `node_failure` | 5 | 5 | 7 | 20 | 4 |

### Validacao de plano

Um plano so vale se for **executavel passo a passo** e **atingir o objetivo**. O metodo `Plan.validate()` reexecuta o plano desde o estado inicial e aponta o primeiro passo inaplicavel, com a precondicao que faltou. Dois testes corrompem planos de proposito: `test_plan_validation_catches_a_corrupted_plan` remove a autorizacao e obtem *not applicable*; `test_plan_validation_catches_a_plan_that_stops_short` remove o encerramento e obtem *does not satisfy the goal*.

### Integracao com a busca A*

`reroute_traffic` exige `alternate-route(?n)`. Esse literal **nao e inventado**: quando o diagnostico e congestionamento, [`problem_from_diagnosis`](../../software/aisg/planning/domain_restoration.py) consulta o A* sobre a topologia, evitando o no afetado. Se nao houver rota, o literal nao entra no estado inicial, a acao fica inaplicavel e o planejador **falha honestamente** em vez de propor um desvio impossivel.

Tres testes cobrem o caminho: `test_rerouting_is_only_planned_when_a_real_alternative_route_exists`, `test_without_an_alternative_route_the_reroute_action_is_unavailable` e `test_no_restoration_is_claimed_when_one_fault_cannot_be_resolved` — este ultimo garante que, com uma falha sem reparo disponivel, o planejador falha em vez de corrigir as outras e declarar servico restaurado.

### O que o grafo de planejamento diz sobre este dominio

O modulo [`planning_graph.py`](../../software/aisg/planning/planning_graph.py) **nao e um quarto planejador**: ele constroi o grafo de planejamento (Blum e Furst, 1997) e o usa para interrogar o dominio escrito a mao. Sobre o problema de `mac-contention` num no:

| Pergunta | Resposta |
|---|---|
| Acoes aterradas | 13 |
| Ponto fixo | nivel 7 |
| Limite inferior do plano | 6 (o plano real tem 7 acoes) |
| Pontos de escolha | **nenhum** |
| Violacoes do invariante de sucesso | **nenhuma** |
| Operadores mortos | 6 — os reparos das falhas **nao** diagnosticadas |

Os operadores mortos encolhem conforme mais falhas entram no problema: 6 com uma falha, 5 com duas, **0** com as sete. Nao e um defeito — e o grafo dizendo que um reparo sem a falha correspondente nunca pode disparar.

O metodo, as quatro perguntas e a analise que reprovou uma versao anterior do dominio estao em [`planner-design-process.md`](planner-design-process.md).

### Como executar

```bash
aisg plan --diagnosis mac_contention --node SAF_02 --solver both --trace
aisg plan --diagnosis congestion --node SAF_02 --solver astar --heuristic zero
aisg plan --diagnosis rf_interference --node SAF_02 --solver gps --trace
aisg pipeline --case congestion --node SAF_01 --target ER_03
```

---

## English

### Problem

The expert system diagnosed a fault and recommended an action. **In what sequence should it be carried out?** Nothing may change the scenario before authorisation, and changing a scenario *parameter* requires stopping the run in progress. Goal: `service-restored(N)` and `logged(N)`.

### STRIPS: the representation

STRIPS (Fikes and Nilsson, 1971) represents an action by **preconditions**, an **add list**, and a **delete list**. A world state is the set of true positive literals; anything absent is false (closed-world assumption). Thirteen operators are defined — see the table in the Portuguese section for costs and requirements.

### Governance as a precondition, not as advice

Every operator that changes the scenario requires `authorized(?n)` — directly, or through the `stop_run` that must precede `start_run`. That makes "we acted without authorisation" an **unreachable** state rather than a runtime check. Only verifying, logging and closing are exempt, because they change nothing. `test_no_scenario_changing_action_precedes_authorisation` checks the invariant across every diagnosis.

### One `cleared-<fault>` literal per fault

`verify_link` requires `cleared-<fault>(?n)` for **every** fault diagnosed in the problem, not one shared flag. With a shared flag, repairing one fault among several unlocked verification and the plan closed the work order with the defect still in place — and `Plan.validate` returned true, because the goal genuinely was satisfied. The full story is in [`planner-design-process.md`](planner-design-process.md), section 6.

### What costs here is stopping the run

Were every action cost 1, planning would be counting steps. What gives planning weight here is not crew travel — it is the cost of **invalidating the run in progress**.

Changing a scenario **parameter** (the path budget, the channel plan) cannot be absorbed by a live run: it must be stopped and restarted, at 2 + 2 = **4**. A **runtime** repair (restarting a node, changing channel, fixing a route) pays none of that.

The consequence is the trade-off that makes planning necessary: **batch the parameter repairs into one stop**. The planner does batch them — one parameter fault costs 11, two cost 12. The second repair costs **+1, not +5**, because it enters a stop already paid for (`test_parameter_changes_share_one_run_restart` asserts exactly one `stop_run` and one `start_run`). With only `node-stopped`, the plan is 5 actions at cost 5 with no stop at all. And stopping is not a free precaution: `verify_link` requires `run-active(?n)`, so the run must be resumed before verification.

### GPS: means-ends analysis

Newell and Simon's GPS plans by **means-ends analysis**: look at the **difference** between the current state and the goal, pick an operator that **reduces** it, recursively satisfy that operator's preconditions, then apply it. Every action exists to remove a concrete difference, which is why the GPS trace reads as a justification rather than a search log. The plan is the stack unwound in reverse.

### GPS's limitations, stated plainly

**GPS is neither complete nor optimal.** It commits to the first operator that reduces the difference and revises only by backtracking on failure. It is also subject to the **Sussman anomaly**: with interacting subgoals, achieving them one at a time can undo earlier work. The implementation takes the minimal defence — after satisfying all subgoals it re-checks whether any was clobbered and **fails explicitly** rather than returning an invalid plan.

A concrete non-optimality, verified in `test_gps_can_be_suboptimal_when_a_cheap_action_has_expensive_preconditions`: GPS orders relevant operators by their **own** cost, ignoring the cost of their **preconditions**. If the cheap action (cost 1) needs an expensive trip (cost 10) while a remote fix costs 3, GPS returns the cost-11 plan and A* finds the cost-3 one.

**But that problem is constructed, and this domain is not it.** Here GPS never loses on cost: `test_gps_matches_a_star_on_every_solvable_fault_combination` compares the **63 combinations** of up to three faults and finds identical costs throughout. The reason is structural, and the planning graph names it: **no literal in this domain has more than one producing operator**, so means-ends analysis has no choice to get wrong. Equal cost is not an identical plan, though — with `node-stopped` and `mac-contention` together both solvers return cost 12 while ordering the independent repairs differently.

That is precisely why both planners live side by side here: one shows the reasoning, the other guarantees the cost.

### A* progression planner

Planning becomes search: a state is the set of true literals, a successor is any applicable action, the step cost is the action's cost, and the goal test is goal inclusion. **The same `astar` function** from the third assignment therefore solves planning — the same function, imported, not an adapted copy.

The `goal_count` heuristic counts unsatisfied goal literals, at most 2. It is admissible **only if** no action satisfies more than one goal literal and every action costs at least 1; in this domain that holds, and we state the condition rather than assume it. The `zero` heuristic reduces A* to uniform-cost search as a control condition, and reaches the same cost. Search effort on the `dual` scenario is tabulated in the Portuguese section.

### Plan validation

A plan is valid only if it is **executable step by step** and **reaches the goal**. `Plan.validate()` re-executes it from the initial state and reports the first inapplicable step with the missing precondition. Two tests deliberately corrupt plans to confirm both failure modes are caught.

### Integration with A* search

`reroute_traffic` requires `alternate-route(?n)`, and that literal is **not invented**: for a congestion diagnosis, `problem_from_diagnosis` consults A* over the topology avoiding the affected node. With no route, the literal is absent, the action is inapplicable, and the planner **fails honestly** instead of proposing an impossible detour — including when one fault among several has no available repair.

### What the planning graph says about this domain

`planning_graph.py` is **not a fourth planner**: it builds the planning graph (Blum & Furst, 1997) and uses it to interrogate the hand-written domain. On a single-node `mac-contention` problem: 13 ground actions, fixpoint at level 7, a goal lower bound of 6 against a real 7-action plan, **no choice points**, **no success-invariant violations**, and 6 dead operators — the repairs for the faults *not* diagnosed. Those shrink to 0 once all seven faults are present. The method and the four questions are in [`planner-design-process.md`](planner-design-process.md).
