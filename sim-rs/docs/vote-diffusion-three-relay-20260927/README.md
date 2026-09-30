# Three upstream relays per producer

Part of the [vote diffusion findings](../vote-diffusion/README.md). The study
fixtures give each block producer two upstream relays; SPO practice is commonly
two public relays plus a third that is not registered on chain. This measures
what that third relay changes, across three seeds and both plausible placements
of it.

Ten runs at 1500 nodes, 458 stake pools, `top-stake-seats`, 400 slots. The
topology is derived from the same fixture the two-relay runs used, so only the
upstream count differs.

## Findings

**The third relay halves the post-gate wait and cuts the gap between the
strategies by 62%.** Quorum times are measured from `t0`; voting opens at
3.000s, so the part a transport controls is the remainder.

| Relays | Strategy | Q95 from t0 | Post-gate | Gap |
|---:|---|---:|---:|---:|
| 2 | Push | 3.334s | 0.334s | — |
| 2 | Pull | 3.850s | 0.850s | +0.516s |
| 3 | Push | 3.161s | 0.161s | — |
| 3 | Pull | 3.358s | 0.358s | **+0.197s** |

**It replicates.** Seeds 0, 1 and 2 agree to within a millisecond, and the two
strategies reach identical availability and endorsement counts at every seed —
pull is not losing certificates, only arriving later.

| Seed | EBs | Q50 / Q75 / Q95 | Push Q95 mean | Pull Q95 mean | Gap | Endorsements |
|---:|---:|---|---:|---:|---:|---:|
| 0 | 26 | 22/26 both | 3.161s | 3.358s | 0.197s | 10 both |
| 1 | 24 | 21/24 both | 3.161s | 3.359s | 0.198s | 9 both |
| 2 | 22 | 19/22 both | 3.161s | 3.358s | 0.197s | 9 both |

**Where the third relay sits does not change the conclusion.** A producer's two
existing relays are in its rack (~0.2 ms); a third is usually not. `sampled`
draws the added link from the topology's own distance-to-latency pool, giving a
~32 ms median; `copy` reuses the producer's existing link latency, modelling a
co-located private relay. They bracket a real deployment:

| Third relay | Push Q95 | Pull Q95 | Gap |
|---|---:|---:|---:|
| `sampled` (~32 ms) | 3.161s | 3.358s | 0.197s |
| `copy` (~0.2 ms) | 3.131s | 3.221s | **0.090s** |

So the honest range for pull's cost at three relays is **0.09–0.20s**, against a
4.000s voting window and a 14.000s certificate-inclusion boundary.

**Bandwidth is unchanged in shape.** Seed 0, 8-byte announcements:

| Strategy | Wire GB | Relay median peak | Relay max peak |
|---|---:|---:|---:|
| Push | 37.33 | 10.65 Mbit/s | 62.72 Mbit/s |
| Pull | 4.71 | 1.32 Mbit/s | 10.96 Mbit/s |

Pull still moves an eighth of the bytes with a six-fold lower peak. The third
relay adds about 14% to both strategies' totals, because there are more links to
carry the same votes.

## Why it helps

Pull's tail, not its mean, set the two-relay penalty: a node had two peers that
might offer it a vote, and it requests from the first offerer with no timeout or
hedging. A third peer gives the first offer more chances to arrive early. Pull's
95th-percentile arrival falls from 0.875s to 0.362s, nearly matching push's
0.407s, while its mean barely moves.

That also means the improvement is a property of the *request rule's* weakness
being masked, not of the rule being fixed. The [model gaps](../vote-diffusion/model-gaps.md)
still apply in full.

## Scope

- One committee mode, one workload, 1500 nodes. No adversary.
- Timing means are conditional on attainment. The fixed 400-slot cutoff leaves
  the newest EBs unfinished, which is why the EB count falls with the seed.
- The `copy` placement is seed 0 only; the seed replication used `sampled`.
- Bounded-fanout arms were also run at cap 8 and are in the bundle. They are a
  [ruled-out direction](../vote-diffusion/README.md#ruled-out) and are not
  reported here.

## Provenance and reproduction

Simulator revision `5c8804e9ee441f7b9d9f92f0526cf01320f8613b`; upstream
configuration pinned to `f307ed5fa7077a32eb470ca3832a34092882bfe3`. The
[evidence bundle](evidence.tar.gz) holds all three run directories with their
inputs, logs, per-node captures and checksum manifests, the queue scripts that
executed them, and the generated comparison.

Evidence archive SHA-256:
`6e4cbe4558d0c4d445ffba4b1e8900e8155189c8e500250f2295cd3dd7aa83ba`.

**One provenance note.** These matrices ran before the runner recorded the
upstream latency mode, so `bp_upstream_latency` was **added to their `runs.csv`
afterwards**, from the queue scripts archived in the bundle. That column is not
covered by any checksum manifest, and the underlying measurements are untouched.
Matrices run after simulator revision `e6d3396` record the mode themselves and
carry a `-copy` run-name token.

To regenerate the comparison from the bundle, from `sim-rs`:

```sh
run_dir=$(mktemp -d)
tar -xzf docs/vote-diffusion-three-relay-20260927/evidence.tar.gz -C "$run_dir"
python3 scripts/compare-vote-matrices.py \
  published=<the follow-up run directory> \
  sampled="$run_dir/vd3-a" copy="$run_dir/vd3-copy" seeds="$run_dir/vd3-seeds" \
  --output "$run_dir/reproduced"
```

To rerun the simulations, check out the revision above and use the saved base
config with `VOTE_STUDY_BP_UPSTREAMS=3`; see
[the study guide](../vote-diffusion-study.md#block-producer-upstream-count).
