# ns-3 — backhaul em duplo acesso / dual-homed backhaul

Programa ns-3 que constrói o backhaul multi-RAT declarado na topologia: uma cadeia de repetidores armazena-e-encaminha em 900 MHz e uma rede LTE privativa alcançando os mesmos roteadores de borda, cada um ligado por cabo a um rádio remoto e a um CPE.

ns-3 program that builds the multi-RAT backhaul declared in the topology: a 900 MHz store-and-forward relay chain and a private LTE network reaching the same edge routers, each wired to one remote radio and one CPE.

Testado com / tested with **ns-3.48**. Cenário e parâmetros sintéticos e nominais. / Synthetic scenario, nominal parameters.

## Modelo / Model

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

## Instalação do zero / Setup from scratch

O ns-3 é instalado como biblioteca e o programa é um projeto CMake independente: nada é copiado nem ligado para dentro da árvore do ns-3.
ns-3 is installed as a library and the program is a standalone CMake project: nothing is copied or linked into the ns-3 source tree.

Verificado em / verified on: Ubuntu 24.04 LTS (WSL2), GCC 13.3, CMake 3.28, ns-3.48.

### 0. Ambiente Linux / Linux environment

Ubuntu 24.04 nativo, ou WSL2 no Windows (`wsl --install -d Ubuntu-24.04`). Todos os comandos abaixo rodam no terminal Linux, não no PowerShell.
Native Ubuntu 24.04, or WSL2 on Windows (`wsl --install -d Ubuntu-24.04`). Every command below runs in the Linux shell, not in PowerShell.

No WSL, a compilação paralela do ns-3 precisa de mais memória que o padrão. Crie `%USERPROFILE%\.wslconfig` e execute `wsl --shutdown` no PowerShell:
Under WSL, the parallel ns-3 build needs more memory than the default. Create `%USERPROFILE%\.wslconfig`, then run `wsl --shutdown` in PowerShell:

```ini
[wsl2]
memory=12GB
swap=8GB
```

### 1. Repositório e pacotes do sistema / Repository and system packages

```bash
sudo apt-get update && sudo apt-get install -y git
git clone https://github.com/fsd-dantas/applied-ai-for-wireless-communication.git ~/applied-ai-for-wireless-communication
export REPO=~/applied-ai-for-wireless-communication
sed 's/#.*//' $REPO/software/ns-3-modules/requirements-ubuntu.txt | xargs sudo apt-get install -y
```

A lista está em [`requirements-ubuntu.txt`](requirements-ubuntu.txt); os pacotes do visualizador NetAnim são opcionais e vêm comentados. No WSL, clonar em `~` compila mais rápido que em `/mnt/c`.
The list is in [`requirements-ubuntu.txt`](requirements-ubuntu.txt); the NetAnim viewer packages are optional and commented out. Under WSL, cloning into `~` builds faster than `/mnt/c`.

### 2. Pacote Python `aisg` / `aisg` Python package

```bash
cd $REPO
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e ".[dev]"
make check
```

O Ubuntu 24.04 não permite `pip install` fora de um ambiente virtual. / Ubuntu 24.04 does not allow `pip install` outside a virtual environment.

### 3. ns-3.48 com a banda 31 / ns-3.48 with band 31

```bash
cd ~
wget https://www.nsnam.org/releases/ns-allinone-3.48.tar.bz2
tar xjf ns-allinone-3.48.tar.bz2
cd ~/ns-allinone-3.48/ns-3.48
patch -p1 < $REPO/software/ns-3-modules/patches/lte-band-31.patch
```

Aplique o patch uma única vez, antes de compilar. Sem ele, execute o programa com `--earfcnDl=2525 --earfcnUl=20525` (banda 5).
Apply the patch once, before building. Without it, run the program with `--earfcnDl=2525 --earfcnUl=20525` (band 5).

### 4. Compilar e instalar o ns-3 / Build and install ns-3

```bash
./ns3 configure --prefix=$HOME/.local/ns3-install --disable-examples --disable-tests
./ns3 build
./ns3 install
```

- O prefixo em `$HOME` dispensa `sudo`. / The prefix under `$HOME` needs no `sudo`.
- As opções são booleanas: `--disable-examples`, não `--enable-examples=off`. Com a forma errada, o `configure` cai nos padrões e ignora também o `--prefix`, e o `install` tenta gravar em `/usr/local`. Confira no resumo: `Examples: OFF` e `Tests: OFF`.
  The options are flags: `--disable-examples`, not `--enable-examples=off`. With the wrong form, `configure` falls back to its defaults and also drops `--prefix`, so `install` tries to write to `/usr/local`. Check the summary for `Examples: OFF` and `Tests: OFF`.
- O ns-3.48 é compilado em C++23 e exige GCC 13 ou mais recente. / ns-3.48 builds as C++23 and needs GCC 13 or newer.

### 5. Compilar o programa / Build the program

```bash
cd $REPO/software/ns-3-modules/dual-homed-backhaul
cmake -B build -S . -Dns3_DIR=$HOME/.local/ns3-install/lib/cmake/ns3
cmake --build build -j "$(nproc)"
```

O [`CMakeLists.txt`](dual-homed-backhaul/CMakeLists.txt) localiza o ns-3 instalado com `find_package(ns3)` e compila em C++23, o mesmo padrão da biblioteca; o pacote exportado pelo ns-3 não declara esse requisito. O executável fica em `build/dual-homed-backhaul`.
[`CMakeLists.txt`](dual-homed-backhaul/CMakeLists.txt) finds the installed ns-3 with `find_package(ns3)` and compiles as C++23, the library's own standard; the package ns-3 exports does not declare that requirement. The executable is `build/dual-homed-backhaul`.

### 6. Exportar os cenários (opcional) / Export the scenarios (optional)

Os arquivos de cenário já estão versionados; para regerá-los a partir da topologia:
The scenario files are already versioned; to regenerate them from the topology:

```bash
cd $REPO && . .venv/bin/activate
aisg ns3-export --out experiments/004-multi-rat-simulation/configuration/dual-homed-60.scn
aisg ns3-export --fault-scenario saf-chain-outage \
  --out experiments/004-multi-rat-simulation/configuration/dual-homed-60-saf-chain-outage.scn
```

Cenários de falha / fault scenarios: `saf-chain-outage`, `dual-outage`, `independent-faults`.

### 7. Executar e verificar / Run and verify

Cada execução é determinística: a saída deve ser idêntica aos resultados versionados do [experimento 004](../../experiments/004-multi-rat-simulation/).
Every run is deterministic: its output must match the versioned results of [experiment 004](../../experiments/004-multi-rat-simulation/).

```bash
cd $REPO
REF=experiments/004-multi-rat-simulation/results/saf-chain-outage/none
OUT=/tmp/ns3-check/saf-chain-outage-none
mkdir -p "$OUT"
software/ns-3-modules/dual-homed-backhaul/build/dual-homed-backhaul \
  --scenario=experiments/004-multi-rat-simulation/configuration/dual-homed-60-saf-chain-outage.scn \
  --outDir="$OUT" --failover=none
for f in sites.csv requests.csv events.csv; do diff -q "$REF/$f" "$OUT/$f" && echo "identical: $f"; done
```

A primeira linha impressa é / the first line printed is `aisg dual-homed backhaul: 60 nodes, 52 point-to-point links, 15 sites, CPE antenna 12 dBi, 30 s simulated`, e os três arquivos devem sair `identical` / and all three files must report `identical`.

## Opções / Options

| Opção / Option | Efeito / Effect |
|---|---|
| `--scenario` | arquivo de cenário (obrigatório) / scenario file (required) |
| `--outDir` | diretório dos resultados / results directory |
| `--failover` | `none`, `local` ou / or `central` |
| `--simTime` | sobrepõe o tempo simulado, em s / overrides the simulated time, in s |
| `--cpeGain` | sobrepõe o ganho da antena do CPE, em dBi / overrides the CPE antenna gain, in dBi |
| `--earfcnDl`, `--earfcnUl` | sobrepõem os EARFCN do LTE / override the LTE EARFCNs |
| `--animate` | grava o traço NetAnim / writes the NetAnim trace |
| `--probe` | cada nó reporta um batimento ao NOC; grava `nodes.csv` (padrão: desligado, para que as execuções versionadas continuem idênticas) / every node reports a heartbeat to the NOC; writes `nodes.csv` (default off, so the versioned runs stay identical) |
| `--probeInterval` | segundos entre batimentos (padrão 1) / seconds between heartbeats (default 1) |
| `--probeStart`, `--probeStop` | janela de medição, em s (padrão 16 e 29) / measurement window, in s (default 16 and 29) |

## Saídas / Outputs

| Arquivo / File | Conteúdo / Contents |
|---|---|
| `sites.csv` | por site: meio primário, pedidos SCADA enviados/recebidos, perda, RTT médio e máximo, telemetria / per site: primary medium, SCADA requests sent/received, loss, mean and max RTT, telemetry |
| `requests.csv` | por consulta SCADA: site, sequência, instante de envio, RTT / per SCADA poll: site, sequence, send time, RTT |
| `events.csv` | falhas injetadas e trocas de meio, com instante e motivo / injected faults and medium switches, with time and reason |
| `flowmon.xml` | FlowMonitor por fluxo / per-flow FlowMonitor |
| `nodes.csv` | com `--probe`: alcançabilidade por nó na janela de medição — batimentos esperados e recebidos, perda, último instante visto, atraso de ida médio / with `--probe`: per-node reachability over the measurement window — heartbeats expected and received, loss, last time seen, mean one-way delay |
| `animation.xml` | traço NetAnim, com `--animate` / NetAnim trace, with `--animate` |

## Limites / Limits

- Remotos sob o mesmo repetidor não disputam o meio: cada salto de rádio é um enlace dedicado. / Remote radios under the same relay do not contend for airtime: each radio hop is a dedicated link.
- Sem MAC proprietário nem modulação adaptativa; retransmissão de enlace não é modelada quadro a quadro. / No proprietary MAC or adaptive modulation; link-layer retransmission is not modelled frame by frame.
- O orçamento de enlace é nominal (log-distância, BPSK) e serve para parametrizar, não para prever um rádio real. / The link budget is nominal (log-distance, BPSK) and parameterises the model; it does not predict a real radio.
