# 3 — Busca A* / A* search

> Roteamento de menor custo no backhaul, com prova de admissibilidade e comparacao
> contra busca em largura, em profundidade, custo uniforme e gulosa.
>
> Least-cost routing over the backhaul, with an admissibility proof and a comparison
> against breadth-first, depth-first, uniform-cost, and greedy search.

Codigo / code: [`software/aisg/search/`](../../software/aisg/search/)

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/fsd-dantas/applied-ai-for-wireless-communication/main/docs/assets/figures/04-astar-dark.svg">
    <img src="https://raw.githubusercontent.com/fsd-dantas/applied-ai-for-wireless-communication/main/docs/assets/figures/04-astar-light.svg" alt="On the left, the optimal path A* finds. On the right, the heuristic, its admissibility and consistency proofs, and the comparison table for five search strategies." width="100%">
  </picture>
</p>

---

## Português

### Problema

Qual o caminho de **menor custo de transporte** entre dois nos da rede? O requisito da disciplina e explicito: o programa deve retornar **o caminho exato** entre o estado inicial e o estado objetivo.

### O algoritmo

O A* (Hart, Nilsson e Raphael, 1968) ordena a fronteira por

```
f(n) = g(n) + h(n)
```

onde `g(n)` e o custo ja pago para chegar a `n` e `h(n)` e a estimativa do custo restante ate o objetivo. As duas metades importam: so `g` da o custo uniforme (otimo, porem cego); so `h` da a busca gulosa (rapida, porem sem garantia).

**Detalhes de implementacao que mudam o resultado:**

- **Desempate.** Empates em `f` sao resolvidos preferindo o maior `g` (no mais profundo) e, depois, a ordem de insercao. Isso mantem as execucoes reproduziveis — importante para uma apresentacao.
- **Reabertura.** Um estado ja fechado e reaberto se surgir um caminho mais barato. Com heuristica consistente isso nunca acontece, mas tratamos o caso geral em vez de supor a consistencia.
- **Custos negativos** sao recusados explicitamente, com erro claro: o A* nao os admite (`test_negative_step_costs_are_refused`).

### A regra da borda do cliente

Um no marcado como **stub** e borda do cliente: uma rota pode **comecar ou terminar** nele, mas nunca **atravessa-lo**. Sem essa regra, a busca encaminharia o trafego de um site pelo roteador de borda de outro — um caminho que o grafo permite e a rede real nao tem.

A regra vive em `RoutingProblem.successors` e vale para todas as estrategias, porque todas consomem a mesma funcao sucessora.

### A heuristica

```
h(n) = distancia_em_linha_reta(n, objetivo) / VELOCIDADE_MAXIMA
```

com `VELOCIDADE_MAXIMA = 150 m/ms`, a maior velocidade efetiva do registro de tipos de enlace (a fibra).

### Prova de admissibilidade

Uma heuristica e **admissivel** se nunca superestima o custo real restante.

Todo salto de `u` a `v` custa

```
custo(u, v) = sobrecarga(tipo) + d(u, v) / (velocidade(tipo) * qualidade)
```

Como `sobrecarga >= 0`, `qualidade <= 1` e `velocidade(tipo) <= VELOCIDADE_MAXIMA` para todo tipo, segue que

```
custo(u, v) >= d(u, v) / VELOCIDADE_MAXIMA
```

Somando ao longo de qualquer caminho de `n` ate o objetivo, o custo total e ao menos a **distancia total percorrida** dividida por `VELOCIDADE_MAXIMA`. Pela desigualdade triangular, a distancia total percorrida e ao menos a distancia em linha reta. Logo

```
custo_otimo(n, objetivo) >= d(n, objetivo) / VELOCIDADE_MAXIMA = h(n)     ∎
```

### Prova de consistencia

Uma heuristica e **consistente** se `h(u) <= custo(u, v) + h(v)` para toda aresta.

Pela desigualdade triangular, `d(u, objetivo) <= d(u, v) + d(v, objetivo)`. Dividindo por `VELOCIDADE_MAXIMA`:

```
h(u) <= d(u, v)/VELOCIDADE_MAXIMA + h(v) <= custo(u, v) + h(v)     ∎
```

A consistencia implica a admissibilidade e garante que nenhum no precise ser reaberto.

**Isto nao e acidente.** O modelo de custo do dominio foi **projetado** para que a prova se sustente: as distancias sao derivadas das coordenadas (nunca armazenadas em separado, para que geometria e heuristica nao possam divergir) e o custo tem um termo proporcional a distancia com velocidade limitada.

**E verificado, nao apenas argumentado.** `test_heuristic_is_admissible_for_every_source_goal_pair` e `test_heuristic_is_consistent` percorrem **todos** os pares origem-objetivo e todas as arestas, **nos dois cenarios empacotados** (`simulated`, 30 nos; `dual`, 60 nos).

**E o oraculo e independente.** `test_astar_matches_an_independent_reference_on_every_ordered_pair` confere o custo do A* contra **Floyd-Warshall**, escrito dentro do proprio teste. Conferir o A* contra o custo uniforme seria circular: `uniform_cost` e literalmente `astar` com `h = 0`, logo um defeito no laco principal, na fila de prioridade ou na reconstrucao do caminho corromperia os dois de forma identica e o teste ainda passaria. O Floyd-Warshall honra a mesma regra da borda do cliente — seu laco intermediario **e** a escolha do no de passagem, entao recusar um stub como intermediario e uma unica clausula de guarda.

### Resultado: `NOC` → `ER_03`

Cenario `dual` (60 nos).

| Estrategia | Passos | Custo (ms) | Expandidos | Gerados | Pico da fronteira | Otimo? |
|---|---|---|---|---|---|---|
| Largura (BFS) | 4 | 453,51 | 15 | 40 | 12 | em passos |
| Profundidade (DFS) | 4 | 453,51 | 7 | 16 | 6 | nao |
| Custo uniforme | 5 | **360,35** | 28 | 62 | 12 | **sim** |
| Gulosa | 5 | **360,35** | **7** | 21 | 10 | aqui sim, por sorte |
| **A\*** | 5 | **360,35** | 23 | 50 | 14 | **sim** |

**A busca em largura minimiza saltos, nao custo.** Ela acha um caminho de **4** saltos que custa 453,51 ms; o A* acha um de **5** saltos que custa 360,35 ms. Menos saltos, 26% mais caro — porque a largura conta um salto de fibra e um salto de radio armazena-e-encaminha como iguais. **O meio decide, nao a contagem de saltos.**

**O A\* alcanca o mesmo otimo do custo uniforme expandindo menos nos** (23 contra 28, 17,9% a menos). A heuristica nao muda a resposta; muda o trabalho para chega-la.

**A gulosa acerta aqui — por sorte, nao por garantia.** Ela expande apenas 7 nos e devolve o caminho otimo. Isso nao e uma propriedade da busca gulosa: e uma coincidencia deste par. A secao seguinte mostra o par em que ela erra.

O caminho otimo evita inteiramente a cadeia armazena-e-encaminha e desce pela sobreposicao LTE:

```
NOC -> eNB_A -> RELAY_1 -> RELAY_5 -> CPE_03 -> ER_03        360,35 ms

salto                  meio                  qual.   custo(ms)   acum.(ms)
NOC -> eNB_A           fibra optica           0,98       60,00       60,00
eNB_A -> RELAY_1       LTE privativo          0,90      128,73      188,73
RELAY_1 -> RELAY_5     LTE privativo          0,90       86,33      275,05
RELAY_5 -> CPE_03      LTE privativo          0,69       76,65      351,70
CPE_03 -> ER_03        ethernet local         1,00        8,65      360,35
```

O caminho mais curto em saltos — o que a busca em largura devolve — usa a malha de 900 MHz:

```
NOC -> SAF_01 -> SAF_02 -> RM_03 -> ER_03                    453,51 ms
```

### Quando a heuristica erra: `NOC` → `ER_04`

| Estrategia | Passos | Custo (ms) | Expandidos | Gerados | Pico da fronteira | Otimo? |
|---|---|---|---|---|---|---|
| Largura (BFS) | 5 | 600,62 | 29 | 69 | 17 | nao |
| Profundidade (DFS) | 5 | 600,62 | 14 | 26 | 6 | nao |
| Custo uniforme | 5 | **322,10** | 21 | 48 | 12 | **sim** |
| Gulosa | 5 | 600,62 | **8** | 20 | 8 | **nao** |
| **A\*** | 5 | **322,10** | 18 | 44 | 14 | **sim** |

**A gulosa e a mais rapida e esta errada.** Expande 8 nos contra 18 do A* — menos da metade do trabalho — e devolve um caminho **1,87 vez mais caro** (600,62 contra 322,10). E o argumento mais direto a favor do termo `g(n)`: sem ele, a busca persegue a proximidade geometrica do objetivo e ignora o que ja gastou para chegar ali.

Este e o par que o teste `test_greedy_is_fast_but_can_be_suboptimal` usa, precisamente porque `NOC` → `ER_03` nao exibe a falha.

### Quanto a heuristica economiza, somado a todos os pares

Um unico par pode ser sorte. Somando os nos expandidos sobre **todos** os pares ordenados de cada cenario:

| Cenario | Nos | Pares ordenados | A\* expandidos | Custo uniforme | Economia |
|---|---|---|---|---|---|
| `simulated` | 30 | 870 | 10 310 | 13 920 | **25,9%** |
| `dual` | 60 | 3 540 | 99 963 | 109 740 | **8,9%** |

**A vantagem ENCOLHEU quando o grafo cresceu** — o oposto da intuicao de que a heuristica compensa mais em grafos maiores.

Uma hipotese, declarada como hipotese e **nao medida**: o cenario `dual` e uma estrela de LTE privativo com muitos sites em stub, e nele a distancia em linha reta prediz mal o custo de transporte, porque o meio barato e um salto LTE longo e o meio caro e um salto de radio curto. No `simulated`, com tres setores geograficamente separados, a geometria acompanha melhor o custo. Verificar essa explicacao exigiria medir a correlacao entre `h(n)` e `h*(n)` por cenario, o que ainda nao foi feito.

O que **esta** garantido, e testado, e a direcao: `test_astar_never_expands_more_nodes_than_uniform_cost` verifica que o total do A* nunca supera o do custo uniforme, em ambos os cenarios. Uma heuristica consistente so pode ajudar; quanto ela ajuda depende do grafo.

**Como reproduzir, e o que ainda falta.** Os dois percentuais acima somam `expanded` do A* e do custo uniforme sobre todos os pares ordenados de cada cenario. Nenhum comando da CLI faz essa soma: `aisg --topology simulated route --compare` compara **um unico par**, nao o agregado. O teste citado verifica a desigualdade, nao o percentual. Enquanto nao existir um script ou teste que recalcule esses dois numeros, eles sao um resultado **declarado, nao reproduzivel por comando** deste repositorio.

### Heuristicas aprendidas: onde o aprendizado de maquina entraria

O repositorio nao usa aprendizado de maquina, e a razao declarada em
[`expert-system.md`](expert-system.md) — a ausencia de dados rotulados de
falha — vale para o **diagnostico**, nao para a heuristica.

Aprender `h(n)` e uma tarefa de natureza diferente:

| | Diagnosticar a causa | Aprender a heuristica |
|---|---|---|
| Alvo | Rotulo de falha | `h*(n)`, o custo real restante |
| Origem do rotulo | Medicao em campo | **Calculavel**: custo uniforme a partir do objetivo |
| Precisa de instrumento de degradacao | Sim | **Nao** |
| Quantidade de exemplos | Zero hoje | Ilimitada — um por par no grafo |

Ou seja: a supervisao e **gratuita e exata**. O obstaculo que impede aprender o
diagnostico simplesmente nao existe aqui.

**O que realmente impede o uso direto e a admissibilidade.** Uma heuristica
obtida por regressao pode **superestimar** o custo restante, e nesse caso o A*
continua funcionando e passa a devolver caminhos subotimos **sem avisar** — o
mesmo modo de falha silenciosa discutido em [`planning.md`](planning.md).

Tres formas de conviver com isso, em ordem de garantia:

1. **Como criterio de desempate apenas.** A ordenacao principal continua sendo
   `g + h_admissivel`; a heuristica aprendida so decide empates. A otimalidade e
   preservada exatamente.
2. **Busca limitadamente subotima** (A* ponderado, *focal search*). Mantem-se a
   heuristica admissivel para o limite e usa-se a aprendida para ordenar dentro
   da faixa. Perde-se a otimalidade, mas com **fator de garantia declarado**.
3. **Regressao com perda assimetrica**, penalizando mais a superestimacao. Reduz
   a violacao, mas **nao a elimina** — nao ha garantia, apenas tendencia.

**Onde isso pagaria mais.** Nao no roteamento: a distancia em linha reta ja e
barata e, no `simulated`, ja economiza um quarto do trabalho. O ganho estaria no
**planejador**, onde a heuristica `goal_count` vale no maximo 2 — o objetivo tem
dois literais, `service-restored(?n)` e `logged(?n)` — e o espaco de estados nao
tem geometria a explorar.

**O repositorio ja tem o instrumento de medida.** Os testes de admissibilidade
percorrem todos os pares origem-objetivo dos dois cenarios. Aplicados a uma
heuristica aprendida, deixam de ser apenas uma protecao e passam a medir *quantas
vezes* ela viola a admissibilidade e *em quanto* — que e precisamente o resultado
que um experimento desses precisa reportar.

### Falhas e recalculo de rota

Um enlace pode ser retirado de servico em tempo de execucao (`--disable-link A-B`) e um no pode ser excluido da rota (`--avoid`). E assim que a integracao com o planejador funciona: quando o plano inclui desviar trafego, a rota e recalculada evitando o no afetado.

```bash
aisg route --from NOC --to ER_03 --disable-link NOC-eNB_A
```

Sem o primeiro salto da sobreposicao LTE, o custo otimo sobe e o caminho passa a usar a cadeia armazena-e-encaminha:

```
antes:   NOC -> eNB_A -> RELAY_1 -> RELAY_5 -> CPE_03 -> ER_03      360,35 ms
depois:  NOC -> SAF_01 -> SAF_02 -> RM_03 -> ER_03                  453,51 ms
```

O teste `test_disabling_a_link_changes_the_optimal_route` verifica exatamente isso; `test_avoiding_a_node_excludes_it_from_the_path` verifica o `--avoid`; e `test_search_reports_failure_when_the_goal_is_isolated` verifica que a busca **declara a falha** em vez de devolver um caminho invalido quando o objetivo fica isolado.

### O mesmo A* resolve os dois problemas

A busca e definida sobre um **problema abstrato** (estado inicial, teste de objetivo, funcao sucessora). Por isso a mesma funcao `astar` serve ao roteamento **e** ao planejamento do trabalho 2. Uma implementacao, dois espacos de estados.

O modulo ainda oferece `iterative_deepening`, que combina a memoria da busca em profundidade com a completude da busca em largura: `test_iterative_deepening_finds_the_shallowest_solution` confirma que ele encontra uma solucao com o mesmo numero de passos que a busca em largura.

### Como executar

```bash
aisg route --from NOC --to ER_03 --compare --expansion
aisg route --from NOC --to ER_04 --compare
aisg route --from NOC --to ER_03 --avoid RELAY_5
aisg route --from NOC --to ER_03 --disable-link NOC-eNB_A
aisg --topology simulated route --compare
```

---

## English

### Problem

What is the **least transport cost** path between two nodes? The course requirement is explicit: the program must return **the exact path** between the initial and the goal state.

### The algorithm

A* (Hart, Nilsson and Raphael, 1968) orders the frontier by `f(n) = g(n) + h(n)`, where `g` is the cost already paid and `h` estimates the cost remaining. Both halves matter: `g` alone is uniform-cost search (optimal but blind); `h` alone is greedy search (fast but unguaranteed).

Implementation details that change the outcome: ties on `f` break towards the larger `g` and then insertion order, keeping runs reproducible; a closed state is re-opened if a cheaper path appears (never needed with a consistent heuristic, but we handle the general case); and negative step costs are refused with a clear error.

### The customer-edge rule

A node marked **stub** is customer edge: a route may begin or end there but never cross it. Without the rule, search would carry one site's traffic through a neighbouring site's edge router — a path the graph allows and the real network does not. The rule lives in `RoutingProblem.successors`, so every strategy inherits it.

### The heuristic and its proofs

```
h(n) = straight_line_distance(n, goal) / MAX_SPEED       MAX_SPEED = 150 m/ms
```

**Admissibility.** Every hop costs `overhead + d(u,v) / (speed * quality)`. Since `overhead >= 0`, `quality <= 1`, and `speed <= MAX_SPEED`, each hop costs at least `d(u,v) / MAX_SPEED`. Summing over any path, the total is at least the total travelled distance over `MAX_SPEED`, which by the triangle inequality is at least the straight-line distance over `MAX_SPEED`. Hence `h(n)` never overestimates. ∎

**Consistency.** By the triangle inequality `d(u, goal) <= d(u, v) + d(v, goal)`; dividing by `MAX_SPEED` gives `h(u) <= cost(u,v) + h(v)`. ∎ Consistency implies admissibility and guarantees no node needs re-expansion.

**This is not an accident.** The domain's cost model was *designed* so the proof holds — distances are derived from coordinates so geometry and heuristic cannot disagree.

**And it is verified against an independent oracle.** Admissibility and consistency are checked over every source-goal pair and every edge, in **both** bundled scenarios. A*'s costs are checked against **Floyd-Warshall**, written inside the test: comparing against uniform cost would be circular, since `uniform_cost` is literally `astar` with `h = 0` and a defect in the shared main loop would corrupt both identically. The reference honours the same customer-edge rule.

### Results

See the tables in the Portuguese section. Two pairs are needed, because no single pair shows every lesson:

1. **`NOC` → `ER_03`: breadth-first minimises hops, not cost** — 4 hops costing 453.51 ms against A*'s 5 hops at 360.35 ms. Fewer hops, 26% dearer, because it counts a fibre hop and a store-and-forward radio hop alike. The medium decides. A* reaches the same optimum as uniform cost while expanding 23 nodes against 28 — 17.9% fewer. Greedy is right here too, on 7 expansions, but by luck rather than guarantee.
2. **`NOC` → `ER_04`: greedy is fastest and wrong** — 8 nodes expanded against A*'s 18, for a path 1.87x more expensive (600.62 against 322.10). The most direct argument for the `g(n)` term. This is the pair `test_greedy_is_fast_but_can_be_suboptimal` uses, precisely because `ER_03` does not expose the failure.

### How much the heuristic saves, over every pair

Summed over every ordered pair: **25.9%** fewer expansions than uniform cost on `simulated` (30 nodes, 870 pairs), but only **8.9%** on `dual` (60 nodes, 3540 pairs). **The advantage shrank as the graph grew**, against the intuition that a heuristic pays off more on larger graphs.

A hypothesis, stated as a hypothesis and *not* measured: `dual` is a private-LTE star with many stub sites, where straight-line distance predicts transport cost poorly because the cheap medium is a long LTE hop and the expensive one is a short radio hop. Confirming it would mean measuring the correlation between `h(n)` and `h*(n)` per scenario, which has not been done.

What *is* guaranteed and tested is the direction: `test_astar_never_expands_more_nodes_than_uniform_cost` checks that A*'s total never exceeds uniform cost's, in both scenarios. A consistent heuristic can only help; how much it helps depends on the graph.

### Failures and re-routing

A link can be taken out of service at runtime (`--disable-link A-B`) and a node excluded from the route (`--avoid`). That is how the planner integration works: when the plan includes rerouting, the route is recomputed avoiding the affected node. Removing `NOC-eNB_A` raises the optimal cost from 360.35 ms to 453.51 ms and moves the route onto the 900 MHz store-and-forward chain.

### One A* for both problems

Search is defined over an **abstract problem** (initial state, goal test, successor function), so the same `astar` function serves routing **and** the planning of assignment 2. One implementation, two state spaces.
