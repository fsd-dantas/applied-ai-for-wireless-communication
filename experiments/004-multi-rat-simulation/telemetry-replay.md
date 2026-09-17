# Recovery from measured telemetry

This experiment applies a blackboard medium-switch recommendation to ns-3 and
compares SCADA replies with a matched run without intervention. It is a two-pass
causal replay, not a controller connected to a running simulator. The current
driver uses the bundled `dual` topology and starts with `saf-chain-outage`.

1. Remove every precomputed `failover` command from the input scenario.
2. Run the plant without intervention until 30 s. Heartbeats are sent during
   16–24 s; arrivals are collected until the measurement run stops.
3. Diagnose using only `nodes.csv` and the declared topology. Commanded faults
   and `events.csv` are not inputs to the diagnosis.
4. Schedule only the inferred `switch_medium` decisions at 31 s. The one-second
   gap is an assumed actuation delay, not a measured controller latency.
5. Replay both the no-intervention baseline and intervention until 60 s with
   identical seed/run settings and probing. Require identical pre-action node
   telemetry in all three runs.
6. Score polls sent in [31, 58) with a two-second reply deadline. Excluding the
   last two seconds prevents incomplete observations at simulator stop. Report
   each site's loss and the first successful reply after intervention. This
   reply time is sampled recovery evidence, not a continuous availability bound.

From the repository root, in the Linux environment where ns-3 is installed:

```bash
cmake --build software/ns-3-modules/dual-homed-backhaul/build -j 2
PYTHONPATH=software python3 -m aisg.simulation.replay \
  --simulator software/ns-3-modules/dual-homed-backhaul/build/dual-homed-backhaul \
  --scenario experiments/004-multi-rat-simulation/configuration/dual-homed-60-saf-chain-outage.scn \
  --out software/ns-3-modules/dual-homed-backhaul/build/telemetry-replay
```

The output directory must not already exist. Use a new directory for each run.
It contains the two scenario files, raw outputs from all three runs, and
`report.json` with decisions, incidents, paired metrics, commands, seed/run number,
and input-scenario/simulator SHA-256 hashes. Exit status is nonzero if a switched
site does not recover to zero measured post-action loss, another site's loss
increases, or pre-action telemetry differs between runs.

The node itself is not repaired: the intervention restores site traffic by
switching access medium. STRIPS repairs and eco-resolution allocations are not
executed here. Evidence is for one synthetic scenario and one random stream;
it establishes an executable feedback experiment, not statistical superiority.
Probe traffic is present in both comparison arms. Reachability-based diagnosis
assumes the nominal routing model and does not uniquely distinguish all possible
causes of heartbeat silence.

## Measured result

The ns-3 build and all three runs completed with seed 1 / run 1. The blackboard
inferred `SAF_02: node_failure` and recommended moving `ER_06` from `radio900` to
`plte`. Both endpoints switched at 31 s, as recorded in `intervention/events.csv`.

| ER_06, polls sent in [31, 58) | No intervention | Telemetry-derived switch |
|---|---:|---:|
| Requests | 13 | 13 |
| Replies within 2 s | 0 | 13 |
| Loss | 100% | 0% |
| First successful reply after action | None | 1.2409294 s |

No other site's measured loss increased. Pre-action `nodes.csv` is byte-identical
across measurement, baseline and intervention. These are single-run observations,
not confidence bounds.

The [report and raw CSVs](results/telemetry-replay/) preserve all three runs and
both generated scenarios. The archived report retains the original build-directory
command paths; rerunning the command above with a new output directory regenerates
the experiment. Large FlowMonitor XML files remain in the local build output.
