<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/fsd-dantas/applied-ai-for-wireless-communication/main/docs/assets/banner-dark.jpg">
    <img src="https://raw.githubusercontent.com/fsd-dantas/applied-ai-for-wireless-communication/main/docs/assets/banner-light.jpg" alt="Applied AI for Wireless Communication — a knowledge base for wireless AI research. An isometric lattice with energised traces wiring a search tree, a network router, a transmission tower, a gauge, a feedback controller and a network mesh to one AI processor." width="100%">
  </picture>
</p>

# Applied AI for Wireless Communication

**Base de conhecimento de pesquisa e framework de pesquisa para aplicar inteligência artificial a sistemas de comunicação sem fio.**
*Research knowledge base and research framework for applying artificial intelligence to wireless communication systems.*

[![tests](https://github.com/fsd-dantas/applied-ai-for-wireless-communication/actions/workflows/tests.yml/badge.svg)](https://github.com/fsd-dantas/applied-ai-for-wireless-communication/actions/workflows/tests.yml)
[![license: MIT](https://img.shields.io/badge/license-MIT-555555)](LICENSE)
[![wiki](https://img.shields.io/badge/wiki-fundamentos%20%2F%20foundations-555555)](https://github.com/fsd-dantas/applied-ai-for-wireless-communication/wiki)

> **PT-BR** — Compêndio de pesquisa sobre **recomendações justificáveis de diagnóstico, intervenção e roteamento sob hipóteses explícitas** em redes de comunicação multi-RAT de sistemas elétricos inteligentes — LTE privativo e rádio em 900 MHz sobre um núcleo em fibra. Cada experimento declara sua questão, seu método, como executá-lo e como seus resultados são verificados.
>
> **EN** — A research compendium on **justifiable diagnosis, intervention and routing recommendations under explicit assumptions** for multi-RAT smart-grid communication networks — private LTE and 900 MHz radio over a fibre core. Every experiment states its question, its method, how to run it, and how its results are checked.

## Questão de pesquisa / Research question

> Na ausência de dados rotulados de falha, é possível construir um encadeamento **diagnóstico → plano → rota** que seja auditável e verificável?
>
> In the absence of labelled fault data, can a **diagnosis → plan → route** chain be built that is both auditable and verifiable?

Problema, subquestões e metodologia / problem, sub-questions and methodology: [`research/`](research/).

## Experimentos / Experiments

| #   | Experimento / Experiment                                                                                          | Métodos / Methods                                                                                                                        |
| --- | ----------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------- |
| 001 | [Encadeamento simbólico de restauração / Symbolic restoration chain](experiments/001-symbolic-restoration-chain/) | Regras de produção com fatores de certeza, STRIPS e GPS, A\* / Production rules with certainty factors, STRIPS and GPS, A\*              |
| 002 | [Quadro-negro multiespecialista / Multi-expert blackboard](experiments/002-multi-expert-blackboard/)              | Arquitetura blackboard, correlação de incidentes, failover multi-RAT / Blackboard architecture, incident correlation, multi-RAT failover |
| 003 | [Eco-resolução / Eco-resolution](experiments/003-eco-resolution/)                                                 | Agentes reativos: satisfação, agressão, fuga, dependência / Reactive agents: satisfaction, aggression, flight, dependency                |
| 004 | [Simulação multi-RAT em ns-3 / Multi-RAT ns-3 simulation](experiments/004-multi-rat-simulation/)                  | LTE privativo, 900 MHz, injeção de falhas / Private LTE, 900 MHz, fault injection                                                        |

## Organização / Layout

```
research/       problema, questões, metodologia, roteiro / problem, questions, methodology, roadmap
experiments/    um diretório por experimento / one directory per experiment
software/       pacote aisg e testes / aisg package and tests
docs/           primeiros passos, arquitetura, modelo de domínio, figuras / getting started, architecture, domain model, figures
```

Pastas são criadas quando têm conteúdo; o [roteiro](research/roadmap.md) registra o que está planejado.
Folders are created when they have content; the [roadmap](research/roadmap.md) records what is planned.

## Início rápido / Quick start

```bash
python -m pip install -e ".[dev]"
make check
aisg blackboard --scenario dual-outage --experts
```

Mais em / more in [docs/getting-started.md](docs/getting-started.md).

Simulação em ns-3, instalação do zero / ns-3 simulation, setup from scratch: [software/ns-3-modules/README.md](software/ns-3-modules/README.md).

## Dados e configurações abertos / Open data and configurations

Configurações e dados que sustentam os resultados são publicados. Todos os cenários são **sintéticos**: nenhum inventário, endereçamento, identificador ou topologia de campo real. Ver a lista de verificação em [CONTRIBUTING.md](CONTRIBUTING.md).

Configurations and data behind the results are published. Every scenario is **synthetic**: no real inventory, addressing, identifier or field topology. See the checklist in [CONTRIBUTING.md](CONTRIBUTING.md).

## Fundamentos / Foundations

A [wiki](https://github.com/fsd-dantas/applied-ai-for-wireless-communication/wiki) reúne a teoria por trás dos experimentos — raciocínio, busca, planejamento, representação do conhecimento, agentes e aprendizagem.
The [wiki](https://github.com/fsd-dantas/applied-ai-for-wireless-communication/wiki) gathers the theory behind the experiments — reasoning, search, planning, knowledge representation, agents and learning.

## Como citar / How to cite

Use [`CITATION.cff`](CITATION.cff); no GitHub, **Cite this repository** gera BibTeX e APA. / On GitHub, **Cite this repository** generates BibTeX and APA.

## Contribuir / Contributing

[CONTRIBUTING.md](CONTRIBUTING.md) · [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) · [CHANGELOG.md](CHANGELOG.md)

## Autor / Author

Fernando Sabino Dantas.

## Licença / License

[MIT](LICENSE).
