# Análise crítica — *The Comparison between Forward and Backward Chaining*

**Artigo:** AL-AJLAN, A. The Comparison between Forward and Backward Chaining. *International Journal of Machine Learning and Computing*, v. 5, n. 2, p. 106–113, 2015.
**Autor da análise:** Fernando Sabino Dantas.

## Objetivo

Avaliar criticamente as afirmações comparativas de Al-Ajlan (2015) sobre encadeamento progressivo (orientado por dados) e regressivo (orientado por objetivo), testando-as contra medição própria sobre a mesma base de regras do [experimento 001](../../../experiments/001-symbolic-restoration-chain/) deste repositório.

## Questão de pesquisa

A conclusão do artigo — de que o progressivo é mais adequado ao sistema de admissão GAES, pelos critérios de Luger — é sustentada pelas evidências apresentadas? As afirmações qualitativas da Tabela II ("rápido", "lento", "faz poucas perguntas", "testa todas as regras", "explicação não facilitada") se sustentam sob medição?

## Hipótese

O encadeamento regressivo consulta menos fatos e dispara menos regras que o progressivo sobre a mesma base, sem perda de concordância no melhor diagnóstico entre os dois modos. A direção do encadeamento, por si só, não determina se uma conclusão pode ser explicada — a explicabilidade depende de registrar a proveniência de cada conclusão, não do sentido em que as regras são percorridas.

## Tópicos relacionados

[Experimento 001](../../../experiments/001-symbolic-restoration-chain/) (mesma base de 41 regras e mesmo motor de encadeamento) · RQ1 ([`research/research-questions.md`](../../../research/research-questions.md)) · critérios de Luger (2009) · fatores de certeza estilo MYCIN (Shortliffe; Buchanan, 1975).

## Modelo do sistema

O mesmo motor de regras do experimento 001 ([`expert_system/`](../../../software/aisg/expert_system/)), executado nos dois modos — progressivo e regressivo — sobre a base simulada, medido por [`measure_chaining.py`](measure_chaining.py).

## Cenário e premissas

Os 8 casos de diagnóstico da base simulada. No progressivo, os 13 fatos são fornecidos de antemão; no regressivo, o motor pergunta apenas o que o objetivo exige — a mesma premissa do artigo, de que a estratégia adequada depende se os dados chegam antes da pergunta ou se a pergunta guia a coleta.

## Software e versões

`aisg`, versão 0.11.0 — o mesmo pacote e motor de encadeamento do experimento 001; Python 3.10+, sem dependências de terceiros.

## Configuração

`measure_chaining.py` executa os 8 casos nos dois modos sem alterar os limiares (`SIM_THRESHOLDS`) do experimento 001; a resolução de conflito é sempre a primeira regra aplicável, como no artigo original.

## Dados de entrada

41 regras de produção com fatores de certeza, 13 variáveis observáveis, diagnóstico de enlaces de rede — a mesma base simulada do experimento 001, nos mesmos 8 casos.

## Procedimento de execução

```bash
PYTHONPATH=software python literature/systematic-review/al-ajlan-2015/measure_chaining.py
```

## Métricas

Perguntas/fatos consultados, regras disparadas, fatos derivados e concordância no melhor diagnóstico entre os dois modos, médios sobre os 8 casos; fator de certeza (CF) final por caso.

## Resultados

O artigo compara os dois encadeamentos num sistema especialista de admissão em pós-graduação (GAES): aplica ambos a doze regras, percorrendo à mão um caso em cada modo, e resume a comparação numa tabela de atributos (Tabela II). Pelos critérios de Luger — dados fornecidos de antemão, muitos objetivos possíveis, hipótese inicial difícil de formular — conclui que o progressivo seria o mais adequado. O mérito é didático: a escolha depende da natureza do problema, não de superioridade absoluta.

**Inconsistências internas.** A Tabela II classifica o progressivo como *top-down* e o regressivo como *bottom-up*, o inverso da Seção III. Na Seção V.A, os números das regras citadas não correspondem à lista ("R3" é a R2; "R8" é a R10; "R9" é a R5); na Seção III.A, um candidato com GPR menor que 3 dispara a Regra 2, cuja premissa exige GPR maior que 3.

**Erros na revisão de busca.** O A\* é descrito como combinação de busca em profundidade e em largura, quando é uma busca pela estimativa *f*(*n*) = *g*(*n*) + *h*(*n*); afirma-se que a profundidade garante solução, o que falha com ciclos; e que a largura "facilmente perde uma solução", embora seja completa.

**Afirmações sem medição.** "Rápido", "lento", "poucas perguntas" e "testa todas as regras" são afirmados, não medidos, com um único caso por estratégia. A Tabela II diz que o progressivo não facilita explicação; esta, porém, depende da proveniência registrada, não da direção do encadeamento.

**Medição própria** (8 casos, mesma base de 41 regras):

| Medida (média em 8 casos) | Progressivo | Regressivo |
|---|---|---|
| Perguntas / fatos consultados | 13,0 | **7,1** |
| Regras disparadas | 9,4 | **4,1** |
| Fatos derivados | 8,5 | 3,6 |
| Mesmo melhor diagnóstico | 8/8 | 8/8 |

Os números confirmam a direção da Tabela II, mas acrescentam duas nuances que o artigo não discute. **Economia tem custo**: num caso (falha do repetidor a montante), o regressivo para ao atingir certeza suficiente (CF 0,90), enquanto o progressivo acumula toda a evidência (CF 0,97). **O custo relevante depende de quem paga pela pergunta**: se a telemetria já foi coletada, o progressivo é natural para monitoramento contínuo; se cada dado exige medição ou pergunta a um operador, o regressivo evita trabalho. Ambos os modos explicaram suas conclusões, contradizendo a Tabela II quanto à explicação.

**Relação com a disciplina.** Os dois encadeamentos reaparecem ao longo do curso — Expert SINTA (regressivo), meios-fins do GPS (orientado por objetivo), especialistas de quadro-negro (progressivo), A\* (heurística admissível). No diagnóstico de redes, o progressivo serve ao alarme contínuo; o regressivo, à investigação de um incidente; sistemas reais combinam os dois.

A conclusão do artigo para o GAES é razoável, e o critério de adequação ao problema é o ensinamento correto; o suporte, porém, é frágil — inconsistências na numeração das regras, erros na revisão de busca e nenhuma medição. A escolha deveria combinar os critérios de Luger com medidas simples, que mostram tanto a economia do regressivo quanto o seu custo.

## Limitações

Do artigo original: um único caso ilustrativo por estratégia, resolução de conflito sempre pela primeira regra, sem tratamento de incerteza. Da réplica: os 8 casos são do domínio de diagnóstico de rede deste repositório, não do GAES — a concordância medida (8/8) é um teste independente da mesma direção qualitativa da Tabela II, não uma reavaliação do caso original.

## Estado de reprodutibilidade

**Reproduzível.** `measure_chaining.py` é determinístico, sem dado externo além da base já versionada; roda com `PYTHONPATH=software`.

## Material de manuscrito relacionado

[`analise-critica.pdf`](analise-critica.pdf) — versão de 2 páginas, gerada por [`build_pdf.ps1`](build_pdf.ps1) a partir deste arquivo.

## Referências

AL-AJLAN, A. The Comparison between Forward and Backward Chaining. *International Journal of Machine Learning and Computing*, v. 5, n. 2, p. 106–113, 2015. DOI: 10.7763/IJMLC.2015.V5.492.

LUGER, G. F. *Artificial Intelligence*: structures and strategies for complex problem solving. 6. ed. Boston: Pearson, 2009.

RUSSELL, S.; NORVIG, P. *Artificial Intelligence*: a modern approach. 4. ed. Harlow: Pearson, 2021.

SHORTLIFFE, E. H.; BUCHANAN, B. G. A model of inexact reasoning in medicine. *Mathematical Biosciences*, v. 23, n. 3-4, p. 351–379, 1975.

DANTAS, F. S. *applied-ai-for-wireless-communication*: a research knowledge base and research framework for applying artificial intelligence to wireless communication systems. Versão 0.11.0. 2026. Software. Medições: `literature/systematic-review/al-ajlan-2015/measure_chaining.py`.
