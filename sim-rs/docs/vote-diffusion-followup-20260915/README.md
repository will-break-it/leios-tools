# VD-2: BP protection and control size

Part of the [vote diffusion experiment register](../vote-diffusion/README.md). Arm names are defined in [transports.md](../vote-diffusion/transports.md); timing is decomposed in [time-budget.md](../vote-diffusion/time-budget.md); limits are listed in [model-gaps.md](../vote-diffusion/model-gaps.md).

This pilot revisits two assumptions in the [108-run study](../vote-diffusion-results-20260910/README.md): whether bounded fanout should protect BP connections, and how pull changes when announcements and requests exceed the original 8-byte assumption. It adds per-node traffic for every case.

The matrix has ten completed 400-slot runs at 1500 nodes, using top-stake-seats and seed 0. Every push case uses `push`, which marks a vote seen on arrival. `push-late-dedupe`, which marks it seen only after verification and is the order the inspected Haskell prototype uses, is not in this matrix. The 458 BPs carry the voting stake; 1042 relays carry no stake. The topology and load match the original seed-0 reference cases. This is one seed and one committee, so it does not repeat the everyone-votes CPU stress test or establish a generally safe fanout.

## Findings

**Protecting BP connections changes the fanout result.** At all three caps, protection restores the unrestricted-push Q95 and endorsement counts in this pilot. The total cap is unchanged.

| Cap | Q95 unprotected → protected | Endorsements unprotected → protected | Unprotected GB | Protected GB | Protected Q95 mean s |
|---:|---|---|---:|---:|---:|
| 22 | 0/26 → 20/26 | 7 → 8 | 19.470 | 19.621 | 3.335 |
| 16 | 0/26 → 20/26 | 1 → 8 | 14.194 | 14.375 | 3.338 |
| 8 | 0/26 → 20/26 | 0 → 8 | 7.097 | 7.380 | 3.345 |

Unrestricted push sends **32.684 GB** with a **3.334s** Q95 mean. Protected cap 8 sends **7.380 GB**, a **77.4% reduction**, with a **3.345s** mean (0.011s later). All protected cases deliver every generated bundle to at least 95% of nodes. That does not mean every node received every vote. These findings apply to this seed, topology and to `push`. BP protection is untested with `push-late-dedupe`, which the 108-run study found changes endorsement counts under load.

**The bandwidth ratio depends strongly on control-message size.** The following rows are actual simulations. The push references send no control messages and are reused across the three pull sizes.

| Announce / request bytes | Pull vote GB | Unrestricted push / pull bytes | Protected cap 8 / pull bytes | Pull Q95 | Pull Q95 mean s | Endorsements |
|---|---:|---:|---:|---|---:|---:|
| 8/8 | 4.149 | 7.88x | 1.78x | 20/26 | 3.850 | 8 |
| 40/40 | 15.715 | 2.08x | 0.47x | 20/26 | 3.850 | 8 |
| 64/64 | 24.390 | 1.34x | 0.30x | 20/26 | 3.850 | 8 |

**Pull avoids duplicate body transfers in the baseline.** Its **8,927 bundles × 1,499 other nodes = 13,381,573 bodies**, with zero redundant arrivals and one completed verification per accepted arrival. It sends **13,381,573 requests** and **348,055,165 announcements**. The body transfers therefore have the spanning-tree count in this request-from-first run; announcements still flood the mesh. This does not establish the same behavior for other request strategies or network conditions.

At 8/8 bytes, pull traffic comprises **1.258 GB of bodies, 2.784 GB of announcements and 0.107 GB of requests**. Request sizes are included. The 40/40 and 64/64 cases are sensitivity assumptions, not verified wire encodings.

**Absolute node traffic is concentrated at relays, and bounded push has the lowest peak of any arm.** The bundle contains all ten per-node reports; the five below are the arms compared elsewhere in this report.

| Transport | Role | Total sent GB | Median sent MB/node | Max sent MB/node | Median received MB/node | Median peak sent Mbit/s | Max peak sent Mbit/s |
|---|---|---:|---:|---:|---:|---:|---:|
| Unrestricted push | BP | 0.385164 | 0.841 | 0.841 | 1.581 | 0.333 | 0.333 |
| Unrestricted push | relay | 32.298928 | 25.970 | 153.114 | 30.577 | 10.287 | 60.649 |
| Protected cap 8 | BP | 0.385164 | 0.841 | 0.841 | 1.240 | 0.333 | 0.333 |
| Protected cap 8 | relay | 6.994522 | 6.713 | 6.713 | 6.507 | 2.659 | 2.659 |
| Pull 8/8 | BP | 0.079317 | 0.165 | 0.334 | 0.980 | 0.066 | 0.133 |
| Pull 8/8 | relay | 4.070045 | 3.173 | 23.078 | 3.550 | 1.257 | 9.144 |
| Pull 40/40 | BP | 0.340966 | 0.736 | 0.907 | 1.551 | 0.292 | 0.360 |
| Pull 40/40 | relay | 15.374384 | 12.501 | 72.721 | 14.398 | 4.920 | 28.800 |
| Pull 64/64 | BP | 0.537250 | 1.164 | 1.333 | 1.980 | 0.461 | 0.528 |
| Pull 64/64 | relay | 23.852544 | 19.341 | 109.981 | 22.530 | 7.607 | 43.552 |

Protected cap 8 peaks at **2.659 Mbit/s** on its busiest relay, below pull at every tested control size, including 8/8 (9.144). It also reaches Q95 0.505s earlier than pull. Its cost is 1.8x pull's total bytes at 8/8.

Bounded push is flat — every relay forwards exactly eight copies, so its median and maximum peak coincide. Unrestricted push and every pull case keep a heavy tail (60.649 against a 10.287 median; 9.144 against 1.257), because both flood every consumer: one with bodies, the other with announcements.

**Pull replaces copies with smaller copies; it does not remove them.** Pull sends 348,055,165 announcements where unrestricted push sends 347,703,105 bodies. The flood is the same shape. A vote body is 94 bytes, so pull's entire saving is the size ratio of an announcement to a body, and it decays as announcements grow: 11.8x per copy at 8 bytes, 1.5x at 64. Bodies are 30% of pull's traffic at 8/8 and 5% at 64/64.

An earlier revision of this report read that as a case for capping the announcement fanout. **That is withdrawn.** A node that receives no offer sends no request, so capping offers breaks coverage exactly as capping bodies does — and the [108-run study](../vote-diffusion-results-20260910/README.md) shows what that costs: across its 72 capped runs, cap 8 produced zero L1 endorsements and caps 16 and 8 never reached Q50. Offers have to reach everyone.

The bandwidth levers that keep coverage are aggregating offers so one message carries several identifiers, and rate-limiting the **serving** side rather than the offering side, which is the shape EB fetch already uses. Bodies already move along a near-spanning tree with zero redundant arrivals, so there is nothing to save there. VD-5 in the [experiment register](../vote-diffusion/README.md) is where the serving limit gets measured.

No obsolete verifications were measured in these ten runs. The original CPU-stress cases have not been rerun with that instrumentation, so this does not quantify their obsolete work.

All five repeated unprotected 8/8 configurations match their archived protocol results, including quorum counts and times, endorsements, vote generation, traffic and verification. The original 108-run data also still re-extracts unchanged.

## What changed

Protected fanout gives explicitly marked BP connections priority **within the same total cap**. A relay protecting one BP at cap 22 has 21 places left for other consumers. Protection defaults to false, preserving archived input behavior. These cases compare the choice of recipients under one budget; they do not give the protected arm an extra copy.

Announcement and request sizes are independently configurable. The tested pairs are 8/8, 40/40 and 64/64 bytes. Each includes a modeled identifier and application framing, excluding TCP/IP. The larger values are sensitivity assumptions, not measurements of a specific wire encoding. Changing them affects the network scheduler, so these are executed simulations rather than arithmetic repricing of unchanged message counts. Bodies remain 94 bytes in this committee.

The same unrestricted-push run is the reference for all three pull cases. Push sends no vote announcements or requests, so those settings do not change its traffic. Pull uses request-from-first. The reported aggregate totals count sends once; adding receives would count delivered bytes a second time.

The runs keep existing transport behavior for obsolete votes. Obsolete work remains included in the total and is also reported separately. This pilot cannot quantify obsolete work in the heavier everyone-votes case, or under `push-late-dedupe`, which verifies a copy before recording the vote as seen.

## Reading the tables

The [evidence bundle](evidence.tar.gz) contains `breakdown/SUMMARY.md` with quorum availability, exact wire bytes, control-size ratios, message counts, obsolete verification work and per-node distributions. `breakdown/followup.json` retains the full numeric record. Each run has a per-node CSV and summary inside the bundle. The key comparisons are shown above so this PR can be reviewed without opening generated data files.

Q95 means nodes holding 95% of stake each have the votes for a certificate. Each node's certificate threshold is **already 75% of total voting stake** — `quorum-weight-fraction: 0.75` — so a request for "the numbers at a 75% quorum" is answered by every row in this report. Q50 and Q95 vary the *observer*, not the threshold: they ask how widely that 75% quorum has become available. Neither is the percentage of votes delivered. The separate bundle-coverage statistic counts receiving nodes without weighting by stake.

Q95 times are measured from the EB's slot boundary and averaged only over EBs that attain Q95. Equal counts do not prove equal EB identities. The fixed cutoff can leave the newest EBs unfinished; timing alone is not evidence of equal availability.

Per-node peaks use fixed one-second windows and sum outgoing links. Sends are counted when queued and receives when delivered. These are neither instantaneous nor sliding-window link-throughput measurements. Bandwidth limits are 10 Mbit/s per link, not per node. Decimal MB/GB are used throughout.

## Provenance and reproduction

All ten runs use simulator revision `825982b42e519184b5fd890298662ab29797f091`, with an empty source patch and an executable reporting `sim-cli 2.0.1-825982b`. The SHA-256 digest is in `binary.sha256` inside the evidence bundle. Upstream configuration is pinned to `f307ed5fa7077a32eb470ca3832a34092882bfe3`. The runner saved the exact base config, overlays, topology, workload, engine, runner scripts and all checksums.

The historical [single-run capture](../vote-traffic-20260915/README.md) remains unchanged and still discloses its earlier binary-version mismatch. This matrix has matching source and embedded binary revisions.

The analysis scripts are pinned to `e18ff497e95c699008b2fa463b3948afa93b399d` in `analysis-revision.txt`, with individual hashes in `analysis-sha256.json`. Use those scripts or the unchanged copies in this report's repository revision. To reconstruct the saved run directory and reproduce its tables, from `sim-rs`:

```sh
report=docs/vote-diffusion-followup-20260915
run_dir=$(mktemp -d)
tar -xzf "$report/evidence.tar.gz" -C "$run_dir"
python3 scripts/summarize-vote-diffusion-followup.py "$run_dir" \
  --output "$run_dir/reproduced"
```

The summarizer verifies frozen input/log/capture hashes, successful completion, requested duration, topology membership and control-message sizes. It reconciles each per-node capture with the final global summary before generating the tables. `SUMMARY.md`, `followup.json`, and every per-node CSV/summary reproduce byte for byte **at the pinned analysis revision**. The current scripts add a Q75 availability column, which these logs predate, so they print `n/a` there and their `SUMMARY.md` differs by that column. Check out `analysis-revision.txt` to verify the archive byte for byte. The general extractor's `updated_utc` timestamp is not part of this deterministic comparison.

To rerun simulations, check out the simulator revision above in a separate worktree and use the saved base config:

```sh
git worktree add --detach /tmp/leios-vote-sim-825982b \
  825982b42e519184b5fd890298662ab29797f091
cd /tmp/leios-vote-sim-825982b/sim-rs
VOTE_STUDY_CONFIG_REVISION=f307ed5fa7077a32eb470ca3832a34092882bfe3 \
  VOTE_STUDY_SLOTS=400 \
  python3 scripts/vote-diffusion-followup.py "$run_dir/study-config.yaml" \
  /tmp/vote-followup-new 0
```

The focused runner enables per-node capture by default and freezes one executable for the whole matrix. Supply a new output directory. Additional seed numbers repeat the ten-case matrix; they are not part of the data published here.

Evidence archive SHA-256: `094896d65976c826c8fb4df089460b4d010e3d86338be63e1843ea725267e523`. The `artifact-sha256.json` inside verifies every other archived file. The executable itself is not included; its matching embedded version and checksum are retained.
