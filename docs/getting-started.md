# Primeiros passos / Getting started

## Instalação / Install

```bash
git clone https://github.com/fsd-dantas/applied-ai-for-wireless-communication.git
cd applied-ai-for-wireless-communication
python -m pip install -e ".[dev]"
```

Python 3.10+. O núcleo não tem dependências de terceiros. / The core has no third-party dependencies.
Sem instalar / without installing: `PYTHONPATH=software python -m aisg ...`

## Comandos / Commands

```bash
# sistema especialista / expert system
aisg diagnose --case rf_interference --trace --explain
aisg diagnose --interactive --mode backward

# planejamento / planning
aisg plan --diagnosis mac_contention --node SAF_02 --solver both --trace

# busca A* / A* search
aisg route --from NOC --to ER_03 --compare --expansion

# os três em sequência / all three in sequence
aisg pipeline --case congestion --node SAF_01 --target ER_03

# quadro-negro multiespecialista / multi-expert blackboard
aisg blackboard --list
aisg blackboard --scenario dual-outage --experts --explain ER_03

# eco-resolução / eco-resolution
aisg eco --problem blocks
aisg eco --problem blocks --sweep
aisg eco --problem network --scenario saf-chain-outage --trace

# cenário ns-3 do backhaul em duplo acesso / ns-3 scenario of the dual-homed backhaul
aisg ns3-export --out dual-homed-60.scn
```

`ns3-export` roda em qualquer SO, mas compilar e executar o cenário no ns-3 **requer Linux** (Ubuntu nativo ou WSL2 no Windows) — ver / `ns3-export` runs on any OS, but building and running the scenario in ns-3 **requires Linux** (native Ubuntu or WSL2 on Windows) — see [software/ns-3-modules/README.md](../software/ns-3-modules/README.md).

Em inglês / in English: `aisg --lang en ...`

## Testes / Tests

```bash
make check          # ou / or: python -m pytest
```

## Para onde ir / Where next

- [Arquitetura / Architecture](architecture.md)
- [Catálogo de experimentos / Experiment catalogue](experiment-catalogue.md)
- [Questões de pesquisa / Research questions](../research/research-questions.md)
