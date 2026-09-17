# Questões de pesquisa / Research questions

## Questão central / Central question

> **PT-BR** — Na ausência de dados rotulados de falha, é possível construir um encadeamento **diagnóstico → plano → rota** que seja *auditável* — cada conclusão rastreável até a evidência que a sustenta — e *verificável* — cujas propriedades de correção sejam asseguradas por testes, e não apenas afirmadas?
>
> **EN** — In the absence of labelled fault data, can a **diagnosis → plan → route** chain be built that is *auditable* — every conclusion traceable to the evidence supporting it — and *verifiable* — its correctness properties asserted by tests rather than merely claimed?

## Subquestões / Sub-questions

| # | Questão / Question | Experimento / Experiment | Estado / Status |
|---|---|---|---|
| RQ1 | **Representação do conhecimento.** Como codificar julgamento de engenharia sob incerteza mantendo a inferência inspecionável e contestável? / **Knowledge representation.** How can engineering judgement under uncertainty be encoded so the inference stays inspectable and contestable? | [001](../experiments/001-symbolic-restoration-chain/) | respondida / answered |
| RQ2 | **Deliberação.** Como derivar a *ordem* de intervenção, expressando restrições como precondições formais e não como verificações em tempo de execução? / **Deliberation.** How is the *order* of intervention derived, with constraints as formal preconditions rather than runtime checks? | [001](../experiments/001-symbolic-restoration-chain/) | respondida / answered |
| RQ3 | **Otimalidade demonstrável.** Sob que condições a busca informada garante a rota de menor custo, e como demonstrar que a heurística as satisfaz neste domínio? / **Demonstrable optimality.** Under which conditions does informed search guarantee the least-cost route, and how is the heuristic shown to meet them here? | [001](../experiments/001-symbolic-restoration-chain/) | respondida / answered |
| RQ4 | **Cooperação entre especialistas.** Especialistas estreitos sobre um quadro-negro compartilhado explicam incidentes de rede melhor do que uma base única, sem alterar nenhuma conclusão sobre um nó isolado? / **Expert cooperation.** Do narrow experts on a shared blackboard explain network-wide incidents better than a single base, without changing any single-node conclusion? | [002](../experiments/002-multi-expert-blackboard/) | respondida no modelo / answered on the model |
| RQ5 | **Resolução descentralizada.** Agentes reativos (eco-resolução), sob regras explícitas de prioridade e dependência, convergem para uma restauração válida? Como se comparam ao planejador central? / **Decentralised resolution.** Do reactive agents (eco-resolution), under explicit priority and dependency rules, converge to a valid restoration? How do they compare with the central planner? | [003](../experiments/003-eco-resolution/) | respondida no modelo / answered on the model |
| RQ6 | **Integração e verificação em malha fechada.** A telemetria de uma rede multi-RAT simulada sustenta o diagnóstico sem acesso à falha comandada, e as recomendações daí derivadas restauram o serviço que prometem? / **Closed-loop integration and verification.** Does telemetry from a simulated multi-RAT network support diagnosis without access to the commanded fault, and do the recommendations derived from it restore the service they promise? | [004](../experiments/004-multi-rat-simulation/) | respondida no modelo / answered on the model |
