"""Causal, two-pass ns-3 failover evaluation from measured telemetry.

Run with ``python -m aisg.simulation.replay --help`` in the simulator's environment.
The scenario supplies the experimental plant/faults, never diagnostic evidence.
Existing failover commands are removed before every run. Only the measurement
run's blackboard decisions determine the intervention.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import subprocess
from typing import Dict, List, Sequence

from aisg.blackboard import Level
from aisg.domain import load_topology
from aisg.simulation.telemetry import diagnose_run


def portable_command(command: Sequence[str], root: Path) -> List[str]:
    """Record a command without exporting the machine's directory layout.

    ``report.json`` is published alongside the results, and the paths this driver
    runs on are resolved to absolute before use. Recording them verbatim would
    put the author's tree into a public repository, so a path under ``root``
    becomes relative to it and anything outside is reduced to its file name.
    Only the recorded copy is rewritten; the command actually executed keeps the
    resolved paths it needs.
    """
    def render(value: str) -> str:
        path = Path(value)
        if not path.is_absolute():
            return value
        try:
            return path.relative_to(root).as_posix()
        except ValueError:
            return path.name

    rendered: List[str] = []
    for argument in command:
        option, separator, value = argument.partition("=")
        rendered.append(f"{option}={render(value)}" if separator and value
                        else render(argument))
    return rendered


def replay_scenario(text: str, actions, action_at: float) -> str:
    """Replace all scripted failovers; preserve the experimental plant and faults."""
    lines = [line for line in text.splitlines()
             if not line.split("#", 1)[0].strip().startswith("failover ")]
    for action in actions:
        site, medium = action["site"], action["to"]
        if medium not in ("plte", "radio900") or not site or any(c.isspace() for c in site):
            raise ValueError("Invalid failover action")
        lines.append(f"failover {action_at:g} {site} {medium}")
    return "\n".join(lines) + "\n"


def request_metrics(path: Path, start: float, end: float) -> Dict[str, dict]:
    """Score polls by send time in [start, end), with a two-second reply deadline.

    End must leave a full deadline before simulator stop. First successful reply
    is reported as an observed delay from the action, not continuous availability.
    """
    by_site: Dict[str, list] = {}
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            sent = float(row["sent_s"])
            if start <= sent < end:
                rtt = float(row["rtt_ms"]) if row["rtt_ms"] else None
                by_site.setdefault(row["site"], []).append((sent, rtt))
    result = {}
    for site, polls in by_site.items():
        replies = [(sent, rtt) for sent, rtt in polls
                   if rtt is not None and math.isfinite(rtt) and 0 <= rtt <= 2000]
        result[site] = {
            "sent": len(polls), "replied_within_deadline": len(replies),
            "loss_pct": 100 * (len(polls) - len(replies)) / len(polls),
            "first_reply_after_action_s": (
                min(sent + rtt / 1000 for sent, rtt in replies) - start if replies else None
            ),
        }
    if not result:
        raise ValueError("No requests in the scoring window")
    return result


def run_replay(simulator: Path, scenario: Path, out: Path, *,
               observe_until: float = 30, action_at: float = 31,
               stop: float = 60, seed: int = 1, run_number: int = 1) -> dict:
    """Measure, infer, replay and compare; refuse to overwrite an existing run."""
    if not all(math.isfinite(t) for t in (observe_until, action_at, stop)) or not (
        26 < observe_until < action_at < stop - 2
    ):
        raise ValueError("Require 26 < observe_until < action_at < stop - 2")
    simulator, scenario, out = simulator.resolve(), scenario.resolve(), out.resolve()
    # Paths are recorded relative to where the driver was started, which the
    # procedure states is the repository root.
    root = Path.cwd().resolve()
    if not simulator.is_file() or not scenario.is_file():
        raise ValueError("Simulator and scenario must be existing files")
    original = scenario.read_text(encoding="utf-8")
    out.mkdir(parents=True, exist_ok=False)
    clean = out / "baseline.scn"
    clean.write_text(replay_scenario(original, [], action_at), encoding="utf-8")
    commands = []

    def execute(name, input_file, duration, mode):
        directory = out / name
        command = [str(simulator), f"--scenario={input_file}", f"--outDir={directory}",
                   f"--simTime={duration:g}", f"--failover={mode}", "--probe=1",
                   "--probeStart=16", "--probeStop=24", "--probeInterval=1",
                   f"--RngSeed={seed}", f"--RngRun={run_number}"]
        commands.append(portable_command(command, root))
        directory.mkdir()
        with (directory / "stdout.txt").open("w", encoding="utf-8") as log:
            subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, check=True)
        return directory

    measurement = execute("measurement", clean, observe_until, "none")
    inferred = diagnose_run(measurement, load_topology("dual"))
    if not inferred.quiescent:
        raise ValueError("Diagnosis did not reach quiescence; refusing to apply actions")
    actions = [
        {"site": entry.subject, "from": entry.data["from"], "to": entry.data["to"],
         "support": list(entry.support)}
        for entry in inferred.board.entries(Level.ACCESS, key="decision")
        if entry.value == "switch_medium"
    ]
    if not actions:
        raise ValueError("No medium-switch recommendation; this replay cannot test recovery")
    intervention = out / "intervention.scn"
    intervention.write_text(replay_scenario(original, actions, action_at), encoding="utf-8")
    baseline = execute("baseline", clean, stop, "none")
    treated = execute("intervention", intervention, stop, "central")
    # Identical measurements establish the evidence precedes the action in both
    # matched runs. A late probe or a changed random stream invalidates the replay.
    measured_bytes = (measurement / "nodes.csv").read_bytes()
    if any((directory / "nodes.csv").read_bytes() != measured_bytes
           for directory in (baseline, treated)):
        raise ValueError("Pre-action telemetry differs between runs; replay is not comparable")
    before = request_metrics(baseline / "requests.csv", action_at, stop - 2)
    after = request_metrics(treated / "requests.csv", action_at, stop - 2)
    if set(before) != set(after) or any(before[s]["sent"] != after[s]["sent"] for s in before):
        raise ValueError("Baseline and intervention request populations differ")
    comparisons = {
        site: {"baseline": before[site], "intervention": after[site],
               "loss_reduction_percentage_points": before[site]["loss_pct"] - after[site]["loss_pct"]}
        for site in sorted(before)
    }
    recovered = all(
        before[a["site"]]["loss_pct"] > 0 and after[a["site"]]["loss_pct"] == 0
        for a in actions
    )
    no_regressions = all(after[s]["loss_pct"] <= before[s]["loss_pct"] for s in before)
    report = {
        "design": "two-pass causal replay, not live control; dual topology only",
        "observation_stop_s": observe_until, "action_at_s": action_at,
        "scoring_window_s": [action_at, stop - 2], "reply_deadline_s": 2,
        "seed": seed, "run_number": run_number, "actions": actions,
        "incidents": [{"node": e.subject, "diagnosis": e.value}
                      for e in inferred.board.entries(Level.INCIDENT, key="incident")],
        "pre_action_telemetry_identical": True,
        "all_switched_sites_recovered": recovered, "no_loss_regressions": no_regressions,
        "sites": comparisons, "commands": commands,
        "sha256": {"input_scenario": hashlib.sha256(original.encode()).hexdigest(),
                   "simulator": hashlib.sha256(simulator.read_bytes()).hexdigest()},
    }
    (out / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--simulator", required=True, type=Path)
    parser.add_argument("--scenario", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    report = run_replay(args.simulator, args.scenario, args.out)
    print(json.dumps({key: report[key] for key in (
        "actions", "all_switched_sites_recovered", "no_loss_regressions"
    )}, indent=2))
    return 0 if report["all_switched_sites_recovered"] and report["no_loss_regressions"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
