# Como o planejador foi definido / How the planner was defined

> O processo de decisao por tras do dominio STRIPS de restauracao, e a analise
> por grafo de planejamento que o valida.
>
> The decision process behind the STRIPS restoration domain, and the
> planning-graph analysis that validates it.

Codigo / code: [`software/aisg/planning/domain_restoration.py`](../../software/aisg/planning/domain_restoration.py),
[`software/aisg/planning/planning_graph.py`](../../software/aisg/planning/planning_graph.py)
Testes / tests: [`tests/test_planning_graph.py`](../../software/tests/test_planning_graph.py)

---

## Português

### Por que este documento existe

Um domínio de planejamento escrito à mão é uma **hipótese sobre o mundo**, não um
fato. Cada precondição afirma que algo é necessário; cada lista de remoção afirma
que algo deixa de valer. Nenhuma dessas afirmações se verifica sozinha.

A tentação, ao documentar, é narrar: *"escolhemos estes operadores porque
pareciam certos"*. Isso não é falseável e não ajuda ninguém a encontrar o próximo
erro. Este documento faz o contrário: registra as decisões e, em seguida, mostra
as **quatro perguntas** que fazemos ao domínio por meio do grafo de planejamento
— inclusive a pergunta que reprovou uma versão anterior.

### 1. Que pergunta o planejador responde

O sistema especialista termina com um diagnóstico e um fator de certeza. Ele
**não** diz em que ordem agir. Falta a pergunta operacional:

> Dado um diagnóstico em um nó, qual é a sequência de ações de **menor custo** que
> restaura o serviço, respeita a exigência de autorização e termina com o registro
> fechado?

Entrada: um diagnóstico e um nó. Saída: um plano ordenado, com custo acumulado,
verificável passo a passo contra o estado inicial.

### 2. Por que STRIPS, e não um script

Um script (`if diagnóstico == X: faça A, B, C`) resolveria os casos previstos.
STRIPS foi escolhido por três propriedades que um script não tem:

1. **As precondições são declaradas, não implícitas.** `authorized(?n)` como
   precondição dos operadores que alteram o cenário torna o estado "agimos sem
   autorização" **inalcançável**, em vez de sujeito a uma verificação em tempo de
   execução. A restrição passa a ser uma propriedade do espaço de estados.
2. **A hipótese do mundo fechado torna o estado inspecionável.** O estado é o
   conjunto de literais verdadeiros; tudo o que está ausente é falso. Um plano
   pode ser reexecutado e conferido (`Plan.validate`).
3. **Combinações não previstas continuam funcionando.** Duas falhas simultâneas
   não exigem um novo ramo de código — exigem que os operadores se componham. Foi
   exatamente aí que apareceu o defeito descrito na seção 6.

### 3. De onde vieram os predicados

Regra adotada: **um predicado por condição que o simulador consegue comandar.**

O cenário é simulado. Isso é uma vantagem metodológica, não uma
limitação: uma condição *comandada* é repetível e rotulável, ao passo que uma
condição *observada* em campo é apenas provável. O bloco `INDUCIBLE_BY` na base de
conhecimento registra, para cada diagnóstico, como ele é induzido no simulador. Os
predicados de falha do domínio de planejamento são a imagem desse bloco:

| Predicado | Como é comandado no cenário |
|---|---|
| `excess-path-loss(?n)` | orçamento de percurso alterado |
| `mac-contention(?n)` | setores compartilhando canal |
| `node-stopped(?n)` | nó desativado na execução |
| `route-missing(?n)` | rota removida da tabela |

O critério tem uma consequência deliberada: se o simulador não sabe produzir a
condição, ela **não entra no domínio**. Foi assim que `weather` e `rain_fade`
saíram, e foi assim que `cabling-fault` deu lugar a `mac-contention`.

### 4. De onde vieram os operadores

Os operadores não foram inventados: são a **camada 4 do sistema especialista**
promovida a ações. Cada ação recomendada por uma regra `S27`–`S34` tornou-se um
operador, e a exigência de autorização da camada 5 tornou-se a precondição
`authorized(?n)`.

Isso mantém os dois sistemas alinhados por construção. Se uma ação existe no
sistema especialista e não existe no planejador, um dos dois está incompleto — e a
análise da seção 7 detecta o caso simétrico (operadores que existem e nunca podem
disparar).

### 5. O modelo de custo

Os custos são **nominais e não calibrados**, exatamente como o bloco `SIM_THRESHOLDS`
da base de conhecimento. Declaram uma ordem de grandeza relativa, não uma medição:

```
request_authorization  1     stop_run             2
restore_path_budget    1     start_run            2
fix_routing            1     separate_channels    3
restart_node           1     verify_link          1
```

A decisão que importa não é o valor absoluto e sim a **relação**: parar e retomar
a execução custa 4, e cada correção dentro da janela custa entre 1 e 3. É isso que
torna vantajoso **agrupar** correções numa única parada — e o planejador de fato as
agrupa (seção 7).

Se todos os custos fossem 1, planejar seria contar passos, e a distinção entre GPS
e A\* desapareceria.

### 6. A decisão dos literais `cleared-<falha>`, e o defeito que a forçou

**Versão anterior:** todo operador de correção adicionava um único literal
compartilhado, `fault-cleared(?n)`, e `verify_link` exigia esse literal.

**Defeito reportado:** com duas falhas no mesmo nó, corrigir **uma** delas
satisfazia `fault-cleared(?n)`, `verify_link` disparava, e o plano anunciava
serviço restaurado com a segunda falha ainda ativa. `Plan.validate` retornava
verdadeiro — porque o objetivo realmente estava satisfeito. O erro não estava no
planejador: estava no **domínio**.

**Correção:** um literal por falha,

```python
def cleared(fault: str) -> str:
    return f"cleared-{fault}(?n)"

verify_preconditions = ("diagnosed(?n)",) + tuple(cleared(f) for f in faults)
```

A lição generaliza: **um literal compartilhado por vários produtores é um ponto de
escolha disfarçado de invariante.** A seção seguinte transforma essa lição em um
teste.

### 7. Validação pelo grafo de planejamento

O grafo de planejamento (Blum e Furst, 1997) alterna níveis de proposições e
níveis de ações, propagando relações de exclusão mútua. Ele se constrói em tempo
polinomial e — este é o ponto — **é útil sem a busca regressiva do Graphplan**. Não
usamos o Graphplan como planejador; usamos o grafo como **instrumento de análise**
do domínio que escrevemos à mão.

Quatro perguntas, todas asseguradas em `tests/test_planning_graph.py`:

**a) Operadores mortos.** Um operador que não aparece em nenhum nível de ação
nunca pode disparar. Resultado: num problema com uma única falha diagnosticada, os
reparos das **outras** falhas estão mortos — com `mac-contention`, são seis
(`change_channel`, `fix_routing`, `reroute_traffic`, `restart_node`,
`restore_path_budget`, `restore_relay`). O número cai para cinco com duas falhas e
para **zero** com as sete. Não é defeito: é o grafo dizendo que um reparo sem a sua
falha nunca pode disparar, sem que seja preciso ler a lista de operadores.
Verificado em `test_repairs_for_absent_faults_are_dead_operators`.

**b) Pontos de escolha.** Quais proposições têm mais de um operador que as produz?
Resultado: **nenhuma**, nos dois cenários. Essa é a explicação *estrutural* de um
resultado empírico incômodo: comparando as **63 combinações solúveis de até três
falhas**, o GPS devolve exatamente o mesmo custo que o A\* em todas — o número que
`test_gps_matches_a_star_on_every_solvable_fault_combination` afirma. A análise
meios-fins nunca perde aqui porque **não tem escolha para errar**.

> Consequência honesta para a apresentação: a não-otimalidade do GPS é uma
> propriedade real, demonstrada em `test_gps_can_be_suboptimal_...`, mas em um
> problema **construído** para isolá-la. Este domínio não é capaz de mostrá-la.

**c) O invariante de sucesso.** No ponto fixo, `service-restored(?n)` deve ser
mutuamente exclusivo com **toda** falha ainda ativa. Se não for, o domínio permite
declarar sucesso sobre uma falha não corrigida.

Este é o teste que reprova a versão anterior. Reconstruindo o domínio pré-correção:

```
service-restored(N) is not mutex with fault-a(N)
service-restored(N) is not mutex with fault-b(N)
choice points:  fault-cleared(N) <- fix_a, fix_b
```

O grafo não só detecta o defeito como **nomeia a causa**: um literal, dois
produtores. Com os literais por falha, ambas as listas ficam vazias. O bug deixou
de ser um plano ruim que alguém precisou ler e passou a ser uma propriedade que um
teste verifica.

**d) Limite inferior do tamanho do plano.** O primeiro nível em que os objetivos
aparecem simultaneamente e sem exclusão mútua é um limite inferior para o número de
passos paralelos. Comparado ao plano que o A\* devolve, é uma verificação que **não
compartilha código com nenhum dos dois planejadores** — o mesmo papel que
Floyd–Warshall cumpre para o A\* na topologia.

### 8. Limitações

- **O grafo é uma relaxação.** Ele ignora listas de remoção ao propagar
  alcançabilidade. Ausência no grafo prova inalcançabilidade; presença não prova
  alcançabilidade. O nível é um limite inferior, nunca uma promessa.
- **O Graphplan minimiza NÍVEIS, não custo.** Preferiria um plano de 2 níveis a um
  plano mais barato de 3. Não pode substituir o planejador A\* progressivo, e
  nenhuma função aqui tenta.
- **O Graphplan clássico é proposicional.** Os operadores são aterrados sobre os
  objetos antes da análise. Com um nó e 13 operadores isso é trivial; não seria
  para os 30 nós simultaneamente.
- **Os custos não são calibrados.** Nenhuma medição de laboratório os sustenta.
- **O domínio ainda é raso.** Zero pontos de escolha significa que ele não exercita
  o que há de interessante em planejamento. Enriquecê-lo — duas formas de restaurar
  o mesmo serviço, com custos diferentes — é o próximo passo óbvio, e faria o teste
  da seção 7b falhar por vontade própria.

---

## English

### Why this document exists

A hand-written planning domain is a **hypothesis about the world**, not a fact.
Every precondition asserts that something is necessary; every delete list
asserts that something stops holding. None of those assertions checks itself.

The temptation when documenting is to narrate: *"we chose these operators
because they seemed right"*. That is not falsifiable and helps nobody find the
next mistake. This document does the opposite: it records the decisions, then
shows the **four questions** we put to the domain through its planning graph —
including the question that failed an earlier version.

### 1. What question the planner answers

The expert system ends with a diagnosis and a certainty factor. It does **not**
say in what order to act. The operational question is missing:

> Given a diagnosis at a node, what is the **least-cost** sequence of actions
> that restores service, respects the authorisation requirement, and finishes
> with the work order closed?

Input: a diagnosis and a node. Output: an ordered plan with cumulative cost,
verifiable step by step against the initial state.

### 2. Why STRIPS rather than a script

A script (`if diagnosis == X: do A, B, C`) would solve the anticipated cases.
STRIPS was chosen for three properties a script does not have:

1. **Preconditions are declared, not implicit.** `authorized(?n)` on the
   operators that change the scenario makes the state "we acted without
   authorisation" **unreachable**, rather than subject to a runtime check. The
   constraint becomes a property of the state space.
2. **The closed-world assumption makes state inspectable.** A state is the set
   of true literals; anything absent is false. A plan can be re-executed and
   checked (`Plan.validate`).
3. **Unanticipated combinations still work.** Two simultaneous faults do not
   require a new code branch — they require the operators to compose. That is
   exactly where the defect in section 6 appeared.

### 3. Where the predicates came from

The rule adopted: **one predicate per condition the simulator can command.**

The scenario is simulated. That is a methodological advantage rather
than a limitation: a *commanded* condition is repeatable and labellable, while
an *observed* field condition is merely probable. The `INDUCIBLE_BY` block in
the knowledge base records, for each diagnosis, how it is induced in the
simulator. The planning domain's fault predicates mirror it:

| Predicate | How it is commanded in the scenario |
|---|---|
| `excess-path-loss(?n)` | path budget altered |
| `mac-contention(?n)` | sectors sharing a channel |
| `node-stopped(?n)` | node disabled in the run |
| `route-missing(?n)` | route removed from the table |

The criterion has a deliberate consequence: if the simulator cannot produce the
condition, it **does not enter the domain**. That is how `weather` and
`rain_fade` left, and how `cabling-fault` gave way to `mac-contention`.

### 4. Where the operators came from

The operators were not invented: they are **layer 4 of the expert system**
promoted to actions. Each action recommended by an `S27`–`S34` rule became an
operator, and layer 5's authorisation requirement became the `authorized(?n)`
precondition.

This keeps the two systems aligned by construction. If an action exists in the
expert system and not in the planner, one of the two is incomplete — and the
analysis in section 7 detects the symmetric case (operators that exist and can
never fire).

### 5. The cost model

Costs are **nominal and uncalibrated**, exactly like the knowledge base's
`SIM_THRESHOLDS` block. They declare a relative order of magnitude, not a
measurement:

```
request_authorization  1     stop_run             2
restore_path_budget    1     start_run            2
fix_routing            1     separate_channels    3
restart_node           1     verify_link          1
```

The decision that matters is not the absolute value but the **ratio**: stopping
and restarting a run costs 4, while each correction inside the window costs
between 1 and 3. That is what makes it worth **batching** corrections into a
single stop — and the planner does batch them (section 7).

Were every cost 1, planning would be counting steps, and the distinction
between GPS and A\* would vanish.

### 6. The `cleared-<fault>` decision, and the defect that forced it

**Earlier version:** every repair operator added a single shared literal,
`fault-cleared(?n)`, and `verify_link` required that literal.

**Reported defect:** with two faults on the same node, clearing **one** of them
satisfied `fault-cleared(?n)`, `verify_link` fired, and the plan announced
service restored with the second fault still live. `Plan.validate` returned
true — because the goal genuinely was satisfied. The error was not in the
planner: it was in the **domain**.

**Fix:** one literal per fault,

```python
def cleared(fault: str) -> str:
    return f"cleared-{fault}(?n)"

verify_preconditions = ("diagnosed(?n)",) + tuple(cleared(f) for f in faults)
```

The lesson generalises: **a literal shared by several producers is a choice
point disguised as an invariant.** The next section turns that lesson into a
test.

### 7. Validation by planning-graph analysis

The planning graph (Blum & Furst, 1997) alternates proposition levels and action
levels, propagating mutual-exclusion relations. It builds in polynomial time
and — this is the point — **is useful without Graphplan's backward search**. We
do not use Graphplan as a planner; we use the graph as an **analysis instrument**
for the domain we wrote by hand.

Four questions, all asserted in `tests/test_planning_graph.py`:

**a) Dead operators.** An operator appearing in no action level can never fire.
Result: in a problem with a single diagnosed fault, the repairs for the **other**
faults are dead — with `mac-contention`, six of them (`change_channel`,
`fix_routing`, `reroute_traffic`, `restart_node`, `restore_path_budget`,
`restore_relay`). That drops to five with two faults and to **zero** with all
seven. It is not a defect: it is the graph saying that a repair without its fault
can never fire, without anyone reading the operator list. Asserted in
`test_repairs_for_absent_faults_are_dead_operators`.

**b) Choice points.** Which propositions have more than one operator producing
them? Result: **none**, in either scenario. That is the *structural* explanation
for an uncomfortable empirical result: comparing the **63 solvable combinations
of up to three faults**, GPS returns exactly the same cost as A\* in every one —
the count `test_gps_matches_a_star_on_every_solvable_fault_combination` asserts.
Means-ends analysis never loses here because it **has no choice to get wrong**.

> The honest consequence for the presentation: GPS non-optimality is a real
> property, demonstrated in `test_gps_can_be_suboptimal_...`, but on a problem
> **constructed** to isolate it. This domain cannot show it.

**c) The success invariant.** At the fixpoint, `service-restored(?n)` must be
mutually exclusive with **every** still-live fault. If it is not, the domain
permits declaring success over an unrepaired fault.

This is the check that fails the earlier version. Reconstructing the pre-fix
domain:

```
service-restored(N) is not mutex with fault-a(N)
service-restored(N) is not mutex with fault-b(N)
choice points:  fault-cleared(N) <- fix_a, fix_b
```

The graph not only detects the defect, it **names the cause**: one literal, two
producers. With per-fault literals both lists are empty. The bug stopped being a
bad plan somebody had to read and became a property a test verifies.

**d) A lower bound on plan length.** The first level at which the goals appear
together and non-mutex is a lower bound on the number of parallel steps.
Compared against the plan A\* returns, it is a check that **shares no code with
either planner** — the same role Floyd–Warshall plays for A\* on the topology.

### 8. Limitations

- **The graph is a relaxation.** It ignores delete lists when propagating
  reachability. Absence from the graph proves unreachability; presence does not
  prove reachability. A level is a lower bound, never a promise.
- **Graphplan minimises LEVELS, not cost.** It would prefer a 2-level plan to a
  cheaper 3-level one. It cannot replace the A\* progression planner, and no
  function here tries.
- **Classic Graphplan is propositional.** Operators are grounded over the
  objects before analysis. With one node and 13 operators that is trivial; it
  would not be over all 30 nodes at once.
- **The costs are uncalibrated.** No laboratory measurement supports them.
- **The domain is still shallow.** Zero choice points means it does not exercise
  what is interesting about planning. Enriching it — two ways to restore the
  same service, at different costs — is the obvious next step, and would make
  the test in section 7b fail of its own accord.

---

## Referencias / References

- Fikes, R. E., & Nilsson, N. J. (1971). STRIPS: A new approach to the
  application of theorem proving to problem solving. *Artificial Intelligence*,
  2(3–4), 189–208.
- Blum, A. L., & Furst, M. L. (1997). Fast planning through planning graph
  analysis. *Artificial Intelligence*, 90(1–2), 281–300.
- Hoffmann, J., & Nebel, B. (2001). The FF planning system: Fast plan generation
  through heuristic search. *Journal of Artificial Intelligence Research*, 14,
  253–302.
- Newell, A., & Simon, H. A. (1963). GPS, a program that simulates human
  thought. In Feigenbaum & Feldman (Eds.), *Computers and Thought*.
