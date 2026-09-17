"""Recovery replay boundaries and independently specified request metrics."""

from pathlib import Path

import pytest

from aisg.simulation.replay import (
    portable_command,
    replay_scenario,
    request_metrics,
    run_replay,
)


def test_recorded_commands_carry_no_absolute_paths(tmp_path):
    """
    `report.json` is published with the results. The driver resolves every path
    before running, so recording the command verbatim would export the author's
    directory layout into a public repository.
    """
    outside = Path(tmp_path.anchor) / "elsewhere" / "other.scn"
    command = [
        str(tmp_path / "build" / "dual-homed-backhaul"),
        f"--scenario={tmp_path / 'run' / 'baseline.scn'}",
        f"--outDir={tmp_path / 'run' / 'measurement'}",
        "--simTime=30", "--probe=1", "--RngSeed=1",
        f"--other={outside}",
    ]
    rendered = portable_command(command, tmp_path)

    assert rendered[0] == "build/dual-homed-backhaul"
    assert rendered[1] == "--scenario=run/baseline.scn"
    assert rendered[2] == "--outDir=run/measurement"
    # non-path arguments survive untouched
    assert rendered[3:6] == ["--simTime=30", "--probe=1", "--RngSeed=1"]
    # a path outside the root keeps only its name
    assert rendered[6] == "--other=other.scn"
    assert not any(str(tmp_path) in argument for argument in rendered)


def test_replay_removes_scripted_actions_and_preserves_faults():
    plant = "aisg-ns3-scenario 1\nfault 10 node_down SAF_02 -\n  failover 13 ER_06 plte\n"
    clean = replay_scenario(plant, [], 31)
    assert "failover" not in clean
    assert "fault 10 node_down SAF_02 -" in clean
    treated = replay_scenario(plant, [{"site": "ER_06", "to": "radio900"}], 31)
    assert treated.count("failover") == 1
    assert "failover 31 ER_06 radio900" in treated
    assert "failover 13" not in treated


def test_request_metrics_use_send_window_and_deadline(tmp_path):
    requests = tmp_path / "requests.csv"
    requests.write_text(
        "site,sequence,sent_s,rtt_ms\n"
        "ER_06,0,30,10\n"  # before action: excluded
        "ER_06,1,31.2,20\n"
        "ER_06,2,33.2,\n"  # lost
        "ER_06,3,35.2,2001\n"  # deadline miss
        "ER_06,4,58,10\n",  # outside window: excluded
        encoding="utf-8",
    )
    metrics = request_metrics(requests, 31, 58)["ER_06"]
    assert metrics["sent"] == 3
    assert metrics["replied_within_deadline"] == 1
    assert metrics["loss_pct"] == pytest.approx(200 / 3)
    assert metrics["first_reply_after_action_s"] == pytest.approx(0.22)


@pytest.mark.parametrize("action_at", [29, 30, 58, float("nan")])
def test_replay_requires_action_after_observation_and_before_scoring_end(tmp_path, action_at):
    with pytest.raises(ValueError, match="observe_until"):
        run_replay(tmp_path / "simulator", tmp_path / "scenario", tmp_path / "out",
                   action_at=action_at)
    assert not (tmp_path / "out").exists()
