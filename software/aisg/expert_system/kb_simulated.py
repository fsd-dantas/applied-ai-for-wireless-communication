"""
Knowledge base: diagnosis on the SIMULATED wireless scenario.

PT-BR: A base de conhecimento do motor de inferencia. O cenario e simulado: o que
       existe sao nos sem fio num meio compartilhado, e as grandezas que um
       simulador realmente produz.

EN:    The knowledge base the inference engine runs on. The scenario is simulated:
       what exists are wireless nodes on a shared medium, and the quantities a
       simulator actually produces.

O que o cenario simulado permite e proibe / What simulation allows and forbids
-----------------------------------------------------------------------------
Permite: perda de percurso comandada, interferencia co-canal, contencao de MAC,
parada de no, queda de repetidor, ausencia de rota, congestionamento.

Proibe: o que o simulador nao produz. Uma simulacao nao irradia, por exemplo,
portanto nao ha vazamento residual a medir. Uma regra sobre um fenomeno que o
simulador nao produz e regra morta, e regra morta sugere cobertura que a base
nao tem.

Forbidden here: what the simulator does not produce. A simulation does not
radiate, for instance, so there is no residual leakage to measure. A rule about a
phenomenon the simulator cannot produce is a dead rule, and a dead rule suggests
coverage the base does not have.

Por que isto importa para os dados / Why this matters for data
-------------------------------------------------------------
Uma rede de campo nao pode ser aprendida porque nao ha rotulos. Aqui o operador
**comanda** a condicao no simulador, portanto conhece o rotulo por construcao —
e pode repetir a execucao quantas vezes quiser. A simulacao e a unica fonte
neste projeto capaz de produzir dados rotulados em quantidade.

A field network cannot be learned because it has no labels. Here the operator
*commands* the condition in the simulator and therefore knows the label by
construction - and can repeat the run as often as wanted. Simulation is the only
source in this project able to produce labelled data in quantity.
"""

from __future__ import annotations

from typing import Dict, Union

from aisg.domain.diagnoses import DIAGNOSES
from aisg.expert_system.engine import (
    Condition,
    Conclusion,
    KnowledgeBase,
    Operator,
    Rule,
    Variable,
    VariableKind,
)

Number = Union[int, float]

#: NOMINAL, UNCALIBRATED. Replace with distributions measured from simulation
#: runs; the rules that use them do not change.
SIM_THRESHOLDS: Dict[str, Number] = {
    "rssi_poor_dbm": -95.0,
    "rssi_marginal_dbm": -85.0,
    "snr_poor_db": 8.0,
    "snr_marginal_db": 15.0,
    "loss_high_pct": 5.0,
    "loss_low_pct": 1.0,
    "rtt_high_ms": 250.0,
    "load_high_pct": 80.0,
    # Commanded propagation loss, in excess of the scenario's nominal budget.
    "path_loss_nominal_db": 0.0,
    "path_loss_high_db": 20.0,
    # The MAC-level discriminator. On a shared CSMA-CA medium, loss with healthy
    # SNR is contention, not propagation - and only this figure separates them.
    "retry_high_pct": 30.0,
}

#: Intended induction recipes, not a claim of implemented ns-3 support.
#: See the shared contract's simulation capability for actual coverage.
INDUCIBLE_BY: Dict[str, str] = {
    name: contract.induction_recipe for name, contract in DIAGNOSES.items()
}

VALIDITY_PT = (
    "LIMITE DE VALIDADE: base para o CENARIO SIMULADO. Os limiares sao "
    "NOMINAIS e NAO CALIBRADOS ate que existam execucoes medidas. Toda condicao "
    "aqui e COMANDAVEL no simulador — logo, rotulavel e repetivel. Um resultado "
    "obtido aqui vale para o MODELO simulado, nao para radio fisico: o MAC "
    "simulado nao e o MAC proprietario do equipamento real."
)

VALIDITY_EN = (
    "VALIDITY LIMIT: base for the SIMULATED scenario. Thresholds are NOMINAL "
    "and UNCALIBRATED until measured runs exist. Every condition here is "
    "COMMANDABLE in the simulator, and therefore labellable and repeatable. A "
    "result obtained here holds for the SIMULATED model, not for physical radio: "
    "the simulated MAC is not the real equipment's proprietary MAC."
)


def _cond(variable: str, operator: str, value: object) -> Condition:
    return Condition(variable, Operator(operator), value)


def build_simulated_knowledge_base() -> KnowledgeBase:
    """Assemble the simulated-scenario variables and rules."""
    kb = KnowledgeBase(
        name_pt="Diagnostico no cenario simulado",
        name_en="Simulated-scenario diagnosis",
        goal_variables=("diagnosis", "recommended_action", "authorization_required"),
        thresholds=dict(SIM_THRESHOLDS),
        validity_note_pt=VALIDITY_PT,
        validity_note_en=VALIDITY_EN,
    )
    add = kb.add_variable

    # ---- PHY-level evidence ---------------------------------------------
    add(Variable(
        "rssi_dbm", VariableKind.NUMERIC,
        "potencia recebida", "received signal strength",
        bounds=(-120.0, -30.0), unit="dBm",
        prompt_pt="Qual a potencia recebida, em dBm [-120, -30]?",
        prompt_en="What is the received signal strength, in dBm [-120, -30]?",
    ))
    add(Variable(
        "snr_db", VariableKind.NUMERIC,
        "relacao sinal-ruido", "signal-to-noise ratio",
        bounds=(-5.0, 40.0), unit="dB",
        prompt_pt="Qual a relacao sinal-ruido, em dB [-5, 40]?",
        prompt_en="What is the signal-to-noise ratio, in dB [-5, 40]?",
    ))
    # Replaces the bench's commanded attenuation: in a simulator the equivalent
    # knob is the propagation loss added beyond the scenario's nominal budget.
    add(Variable(
        "excess_path_loss_db", VariableKind.NUMERIC,
        "perda de percurso excedente", "path loss beyond nominal",
        bounds=(0.0, 80.0), unit="dB",
        prompt_pt="Quanta perda de percurso acima do nominal foi comandada, em dB [0, 80]?",
        prompt_en="How much path loss beyond nominal was commanded, in dB [0, 80]?",
    ))

    # ---- MAC-level evidence ---------------------------------------------
    # The discriminator. Without it, contention and path loss look identical at
    # the flow level: both show loss. Only the retry rate separates a medium that
    # is busy from a signal that is weak.
    add(Variable(
        "retry_rate_pct", VariableKind.NUMERIC,
        "taxa de retransmissao MAC", "MAC retry rate",
        bounds=(0.0, 100.0), unit="%",
        prompt_pt="Qual a taxa de retransmissao no MAC, em % [0, 100]?",
        prompt_en="What is the MAC-level retry rate, in % [0, 100]?",
    ))

    # ---- flow-level evidence (FlowMonitor) ------------------------------
    add(Variable(
        "packet_loss_pct", VariableKind.NUMERIC,
        "perda de pacotes", "packet loss",
        bounds=(0.0, 100.0), unit="%",
        prompt_pt="Qual a perda de pacotes, em % [0, 100]?",
        prompt_en="What packet loss is observed, in % [0, 100]?",
    ))
    add(Variable(
        "rtt_ms", VariableKind.NUMERIC,
        "atraso de ida e volta", "round-trip delay",
        bounds=(0.0, 5000.0), unit="ms",
        prompt_pt="Qual o atraso de ida e volta, em ms [0, 5000]?",
        prompt_en="What is the round-trip delay, in ms [0, 5000]?",
    ))
    add(Variable(
        "offered_load_pct", VariableKind.NUMERIC,
        "carga oferecida", "offered load",
        bounds=(0.0, 200.0), unit="%",
        prompt_pt="Qual a carga oferecida em relacao a capacidade, em % [0, 200]?",
        prompt_en="What is the offered load relative to capacity, in % [0, 200]?",
    ))

    # ---- scenario state --------------------------------------------------
    add(Variable(
        "node_responding", VariableKind.BOOLEAN,
        "no responde", "node responding",
        labels=("yes", "no"),
        prompt_pt="O no responde [yes, no]?",
        prompt_en="Does the node respond [yes, no]?",
    ))
    add(Variable(
        "upstream_relay_reachable", VariableKind.BOOLEAN,
        "repetidor a montante alcancavel", "upstream relay reachable",
        labels=("yes", "no"),
        prompt_pt="O repetidor a montante responde [yes, no]?",
        prompt_en="Does the upstream relay respond [yes, no]?",
    ))
    add(Variable(
        "route_present", VariableKind.BOOLEAN,
        "rota presente para o destino", "route present to the destination",
        labels=("yes", "no"),
        prompt_pt="Existe rota para o destino [yes, no]?",
        prompt_en="Is there a route to the destination [yes, no]?",
    ))
    add(Variable(
        "co_channel_emitter", VariableKind.BOOLEAN,
        "emissor no mesmo canal", "co-channel emitter present",
        labels=("yes", "no"),
        prompt_pt="Ha emissor ativo no mesmo canal [yes, no]?",
        prompt_en="Is another emitter active on the same channel [yes, no]?",
    ))
    add(Variable(
        "nodes_sharing_channel", VariableKind.CATEGORICAL,
        "nos no mesmo canal", "nodes sharing the channel",
        labels=("few", "many"),
        prompt_pt="Quantos nos disputam o canal [few, many]?",
        prompt_en="How many nodes contend for the channel [few, many]?",
    ))
    add(Variable(
        "neighbours_affected", VariableKind.CATEGORICAL,
        "vizinhos afetados", "affected neighbours",
        labels=("none", "one", "many"),
        prompt_pt="Quantos nos vizinhos estao afetados [none, one, many]?",
        prompt_en="How many neighbouring nodes are affected [none, one, many]?",
    ))

    # ---- intermediate ----------------------------------------------------
    add(Variable(
        "signal_quality", VariableKind.CATEGORICAL,
        "qualidade do sinal", "signal quality",
        labels=("good", "marginal", "poor"), askable=False,
    ))
    add(Variable(
        "link_symptom", VariableKind.CATEGORICAL,
        "sintoma do enlace", "link symptom",
        labels=("none", "degraded", "outage"), askable=False,
    ))

    # ---- goals ------------------------------------------------------------
    add(Variable(
        "diagnosis", VariableKind.CATEGORICAL, "diagnostico", "diagnosis",
        labels=tuple(INDUCIBLE_BY), askable=False,
    ))
    add(Variable(
        "recommended_action", VariableKind.CATEGORICAL,
        "acao recomendada", "recommended action",
        labels=(
            "change_channel",
            "restore_path_budget",
            "separate_channels",
            "restart_node",
            "restore_upstream_relay",
            "fix_routing",
            "reroute_traffic",
            "no_action",
        ),
        askable=False,
    ))
    add(Variable(
        "authorization_required", VariableKind.BOOLEAN,
        "exige janela autorizada", "authorised window required",
        labels=("yes", "no"), askable=False,
    ))

    t = SIM_THRESHOLDS
    r = kb.add_rule

    # ---- layer 1: signal quality ------------------------------------------
    r(Rule("S01",
        (_cond("rssi_dbm", "<", t["rssi_poor_dbm"]), _cond("snr_db", "<", t["snr_poor_db"])),
        Conclusion("signal_quality", "poor"), 0.90,
        "Potencia e relacao sinal-ruido abaixo do limiar.",
        "Signal strength and SNR both below threshold."))
    r(Rule("S02",
        (_cond("rssi_dbm", ">=", t["rssi_poor_dbm"]), _cond("rssi_dbm", "<", t["rssi_marginal_dbm"])),
        Conclusion("signal_quality", "marginal"), 0.70,
        "Potencia recebida na faixa de margem estreita.",
        "Received power in the thin-margin band."))
    r(Rule("S03",
        (_cond("snr_db", ">=", t["snr_poor_db"]), _cond("snr_db", "<", t["snr_marginal_db"])),
        Conclusion("signal_quality", "marginal"), 0.60,
        "Relacao sinal-ruido insuficiente para taxa plena.",
        "SNR insufficient for full rate."))
    r(Rule("S04",
        (_cond("rssi_dbm", ">=", t["rssi_marginal_dbm"]), _cond("snr_db", ">=", t["snr_marginal_db"])),
        Conclusion("signal_quality", "good"), 0.90,
        "Potencia e relacao sinal-ruido dentro do esperado.",
        "Signal strength and SNR within expectation."))

    # ---- layer 2: symptom --------------------------------------------------
    r(Rule("S05", (_cond("node_responding", "=", "no"),),
        Conclusion("link_symptom", "outage"), 1.00,
        "No que nao responde e indisponibilidade por definicao.",
        "A node that does not respond is an outage by definition."))
    r(Rule("S06",
        (_cond("node_responding", "=", "yes"), _cond("packet_loss_pct", ">", t["loss_high_pct"])),
        Conclusion("link_symptom", "degraded"), 0.80,
        "No ativo com perda sustentada.",
        "Node up with sustained loss."))
    r(Rule("S07",
        (_cond("node_responding", "=", "yes"), _cond("rtt_ms", ">", t["rtt_high_ms"])),
        Conclusion("link_symptom", "degraded"), 0.70,
        "Atraso acima do limiar.",
        "Delay above threshold."))
    r(Rule("S08",
        (_cond("node_responding", "=", "yes"),
         _cond("packet_loss_pct", "<=", t["loss_low_pct"]),
         _cond("rtt_ms", "<=", t["rtt_high_ms"])),
        Conclusion("link_symptom", "none"), 0.90,
        "No ativo, perda baixa e atraso esperado.",
        "Node up, low loss, delay as expected."))

    # ---- layer 3: diagnosis -------------------------------------------------
    r(Rule("S10",
        (_cond("co_channel_emitter", "=", "yes"), _cond("signal_quality", "=", "poor")),
        Conclusion("diagnosis", "rf_interference"), 0.85,
        "Sinal degradado com emissor ativo no mesmo canal.",
        "Degraded signal with another emitter on the same channel."))
    r(Rule("S11",
        (_cond("co_channel_emitter", "=", "yes"), _cond("neighbours_affected", "=", "many")),
        Conclusion("diagnosis", "rf_interference"), 0.70,
        "Varios nos afetados: causa no meio compartilhado.",
        "Several nodes affected: a cause in the shared medium."))

    r(Rule("S12",
        (_cond("excess_path_loss_db", ">", t["path_loss_high_db"]),
         _cond("signal_quality", "=", "poor")),
        Conclusion("diagnosis", "excess_path_loss"), 0.90,
        "Perda de percurso comandada explica o sinal fraco.",
        "Commanded path loss explains the weak signal."))
    r(Rule("S13",
        (_cond("excess_path_loss_db", ">", t["path_loss_high_db"]),
         _cond("link_symptom", "=", "degraded")),
        Conclusion("diagnosis", "excess_path_loss"), 0.75,
        "Degradacao sob perda de percurso comandada.",
        "Degradation under commanded path loss."))

    # MAC contention: loss WITHOUT a weak signal. This is the wireless failure
    # mode a wired network cannot have, and the retry rate is what reveals it.
    r(Rule("S14",
        (_cond("retry_rate_pct", ">", t["retry_high_pct"]),
         _cond("signal_quality", "!=", "poor"),
         _cond("co_channel_emitter", "=", "no")),
        Conclusion("diagnosis", "mac_contention"), 0.85,
        "Retransmissao alta com sinal saudavel: o meio esta disputado, nao fraco.",
        "High retry with a healthy signal: the medium is contended, not weak."))
    r(Rule("S15",
        (_cond("retry_rate_pct", ">", t["retry_high_pct"]),
         _cond("nodes_sharing_channel", "=", "many")),
        Conclusion("diagnosis", "mac_contention"), 0.75,
        "Muitos nos no mesmo canal com retransmissao alta: contencao de CSMA-CA.",
        "Many nodes on one channel with high retry: CSMA-CA contention."))

    r(Rule("S16", (_cond("node_responding", "=", "no"),),
        Conclusion("diagnosis", "node_failure"), 0.80,
        "No parado no cenario.",
        "The node was stopped in the scenario."))
    r(Rule("S17",
        (_cond("upstream_relay_reachable", "=", "no"), _cond("node_responding", "=", "no")),
        Conclusion("diagnosis", "upstream_relay_failure"), 0.90,
        "Numa cadeia armazena-e-encaminha, a queda do repetidor derruba o que esta a jusante.",
        "In a store-and-forward chain, losing the relay drops what is downstream."))
    r(Rule("S18",
        (_cond("upstream_relay_reachable", "=", "no"), _cond("neighbours_affected", "=", "many")),
        Conclusion("diagnosis", "upstream_relay_failure"), 0.75,
        "Perda simultanea a jusante do mesmo repetidor.",
        "Simultaneous loss downstream of the same relay."))

    r(Rule("S19",
        (_cond("route_present", "=", "no"), _cond("node_responding", "=", "yes")),
        Conclusion("diagnosis", "routing_misconfiguration"), 0.90,
        "No responde mas nao ha rota: o problema e de encaminhamento, nao de radio.",
        "The node responds but there is no route: forwarding, not radio."))

    r(Rule("S20",
        (_cond("offered_load_pct", ">", t["load_high_pct"]),
         _cond("rtt_ms", ">", t["rtt_high_ms"]),
         _cond("signal_quality", "!=", "poor")),
        Conclusion("diagnosis", "congestion"), 0.80,
        "Atraso alto com RF saudavel e carga alta: enfileiramento.",
        "High delay with healthy RF and high load: queueing."))
    r(Rule("S21",
        (_cond("offered_load_pct", ">", t["load_high_pct"]),
         _cond("packet_loss_pct", ">", t["loss_low_pct"]),
         _cond("co_channel_emitter", "=", "no")),
        Conclusion("diagnosis", "congestion"), 0.60,
        "Perda por descarte de fila sob carga alta.",
        "Loss from queue drops under high load."))

    r(Rule("S22",
        (_cond("link_symptom", "=", "none"), _cond("signal_quality", "=", "good")),
        Conclusion("diagnosis", "healthy"), 0.90,
        "Sem sintoma e com sinal bom: linha de base.",
        "No symptom and good signal: the baseline."))

    # ---- counter-evidence ---------------------------------------------------
    r(Rule("S23", (_cond("excess_path_loss_db", "<=", t["path_loss_nominal_db"]),),
        Conclusion("diagnosis", "excess_path_loss"), -0.85,
        "Perda nominal comandada e evidencia CONTRA perda de percurso.",
        "Nominal commanded loss is evidence AGAINST excess path loss."))
    r(Rule("S24", (_cond("co_channel_emitter", "=", "no"),),
        Conclusion("diagnosis", "rf_interference"), -0.70,
        "Nenhum emissor co-canal e evidencia CONTRA interferencia.",
        "No co-channel emitter is evidence AGAINST interference."))
    r(Rule("S25", (_cond("retry_rate_pct", "<=", t["retry_high_pct"]),),
        Conclusion("diagnosis", "mac_contention"), -0.80,
        "Retransmissao baixa e evidencia CONTRA contencao de MAC.",
        "Low retry is evidence AGAINST MAC contention."))
    r(Rule("S26", (_cond("node_responding", "=", "yes"),),
        Conclusion("diagnosis", "node_failure"), -0.90,
        "No que responde e evidencia CONTRA parada de no.",
        "A responding node is evidence AGAINST node failure."))

    # ---- layer 4: recommended action ----------------------------------------
    for rule_id, diagnosis, action, cf, pt, en in (
        ("S27", "rf_interference", "change_channel", 0.90,
         "Mudar de canal afasta o emissor interferente.",
         "Changing channel moves away from the interferer."),
        ("S28", "excess_path_loss", "restore_path_budget", 0.85,
         "Rever a perda comandada e o orcamento de enlace do cenario.",
         "Review the commanded loss and the scenario's link budget."),
        ("S29", "mac_contention", "separate_channels", 0.85,
         "Separar os setores em frequencia reduz a disputa pelo meio.",
         "Separating the sectors in frequency reduces contention for the medium."),
        ("S30", "node_failure", "restart_node", 0.90,
         "Reativar o no parado no cenario.",
         "Restart the node stopped in the scenario."),
        ("S31", "upstream_relay_failure", "restore_upstream_relay", 0.90,
         "Recuperar o repetidor restaura a cadeia a jusante.",
         "Recovering the relay restores the downstream chain."),
        ("S32", "routing_misconfiguration", "fix_routing", 0.90,
         "Corrigir a rota para o destino.",
         "Correct the route to the destination."),
        ("S33", "congestion", "reroute_traffic", 0.80,
         "Desviar trafego alivia a fila enquanto a capacidade nao muda.",
         "Rerouting relieves the queue while capacity is unchanged."),
        ("S34", "healthy", "no_action", 0.90,
         "Nenhuma acao e a acao correta na linha de base.",
         "No action is the right action at the baseline."),
    ):
        r(Rule(rule_id, (_cond("diagnosis", "=", diagnosis),),
               Conclusion("recommended_action", action), cf, pt, en))

    # ---- layer 5: authorisation gate ----------------------------------------
    for rule_id, action in (
        ("S35", "change_channel"),
        ("S36", "restore_path_budget"),
        ("S37", "separate_channels"),
        ("S38", "restart_node"),
        ("S39", "restore_upstream_relay"),
        ("S40", "fix_routing"),
        ("S41", "reroute_traffic"),
    ):
        r(Rule(rule_id, (_cond("recommended_action", "=", action),),
            Conclusion("authorization_required", "yes"), 1.00,
            "Alterar o cenario durante uma campanha exige janela autorizada.",
            "Changing the scenario during a campaign requires an authorised window."))
    r(Rule("S42", (_cond("recommended_action", "=", "no_action"),),
        Conclusion("authorization_required", "no"), 1.00,
        "Nenhuma acao, nenhuma janela.",
        "No action, no window."))

    return kb


#: One case per commandable condition. The case name IS the ground-truth label,
#: because the operator sets the condition before the run.
SIM_CASES: Dict[str, Dict[str, object]] = {
    "rf_interference": {
        "rssi_dbm": -97.0, "snr_db": 6.0, "excess_path_loss_db": 0.0,
        "retry_rate_pct": 45.0, "packet_loss_pct": 12.0, "rtt_ms": 180.0,
        "offered_load_pct": 35.0, "node_responding": "yes",
        "upstream_relay_reachable": "yes", "route_present": "yes",
        "co_channel_emitter": "yes", "nodes_sharing_channel": "few",
        "neighbours_affected": "many",
    },
    "excess_path_loss": {
        "rssi_dbm": -99.0, "snr_db": 5.0, "excess_path_loss_db": 35.0,
        "retry_rate_pct": 20.0, "packet_loss_pct": 9.0, "rtt_ms": 200.0,
        "offered_load_pct": 30.0, "node_responding": "yes",
        "upstream_relay_reachable": "yes", "route_present": "yes",
        "co_channel_emitter": "no", "nodes_sharing_channel": "few",
        "neighbours_affected": "one",
    },
    "mac_contention": {
        "rssi_dbm": -78.0, "snr_db": 22.0, "excess_path_loss_db": 0.0,
        "retry_rate_pct": 62.0, "packet_loss_pct": 8.0, "rtt_ms": 240.0,
        "offered_load_pct": 55.0, "node_responding": "yes",
        "upstream_relay_reachable": "yes", "route_present": "yes",
        "co_channel_emitter": "no", "nodes_sharing_channel": "many",
        "neighbours_affected": "many",
    },
    "node_failure": {
        "rssi_dbm": -110.0, "snr_db": 0.0, "excess_path_loss_db": 0.0,
        "retry_rate_pct": 0.0, "packet_loss_pct": 100.0, "rtt_ms": 5000.0,
        "offered_load_pct": 0.0, "node_responding": "no",
        "upstream_relay_reachable": "yes", "route_present": "yes",
        "co_channel_emitter": "no", "nodes_sharing_channel": "few",
        "neighbours_affected": "none",
    },
    "upstream_relay_failure": {
        "rssi_dbm": -105.0, "snr_db": 3.0, "excess_path_loss_db": 0.0,
        "retry_rate_pct": 0.0, "packet_loss_pct": 100.0, "rtt_ms": 4000.0,
        "offered_load_pct": 0.0, "node_responding": "no",
        "upstream_relay_reachable": "no", "route_present": "yes",
        "co_channel_emitter": "no", "nodes_sharing_channel": "few",
        "neighbours_affected": "many",
    },
    "routing_misconfiguration": {
        "rssi_dbm": -76.0, "snr_db": 24.0, "excess_path_loss_db": 0.0,
        "retry_rate_pct": 5.0, "packet_loss_pct": 100.0, "rtt_ms": 4000.0,
        "offered_load_pct": 10.0, "node_responding": "yes",
        "upstream_relay_reachable": "yes", "route_present": "no",
        "co_channel_emitter": "no", "nodes_sharing_channel": "few",
        "neighbours_affected": "none",
    },
    "congestion": {
        "rssi_dbm": -80.0, "snr_db": 19.0, "excess_path_loss_db": 0.0,
        "retry_rate_pct": 12.0, "packet_loss_pct": 3.0, "rtt_ms": 420.0,
        "offered_load_pct": 130.0, "node_responding": "yes",
        "upstream_relay_reachable": "yes", "route_present": "yes",
        "co_channel_emitter": "no", "nodes_sharing_channel": "few",
        "neighbours_affected": "none",
    },
    "healthy": {
        "rssi_dbm": -74.0, "snr_db": 25.0, "excess_path_loss_db": 0.0,
        "retry_rate_pct": 3.0, "packet_loss_pct": 0.0, "rtt_ms": 35.0,
        "offered_load_pct": 22.0, "node_responding": "yes",
        "upstream_relay_reachable": "yes", "route_present": "yes",
        "co_channel_emitter": "no", "nodes_sharing_channel": "few",
        "neighbours_affected": "none",
    },
}
