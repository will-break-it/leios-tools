# Vote diffusion experiments

How should Linear Leios move vote bundles between nodes? Each experiment below
answers one question, names its arms the same way, and links to frozen evidence.

Read [transports.md](transports.md) first if any arm name is unclear: it gives the
exact forwarding rule behind each name. [time-budget.md](time-budget.md) shows
where the seconds go, and [model-gaps.md](model-gaps.md) states what these runs
do and do not support.

## Register

| ID | Question | Status | Evidence |
|---|---|---|---|
| **VD-1** transport baseline | Does vote streaming stay feasible at 750/1500 nodes, and how do push and pull compare? | done, 108 runs, seeds 0–2 | [results 2026-09-10](../vote-diffusion-results-20260910/README.md) |
| **VD-2** BP protection and control size | Does bounded push need to protect BP links, and how much does pull depend on the announcement size? | done, 10 runs, seed 0 | [follow-up 2026-09-15](../vote-diffusion-followup-20260915/README.md) |
| **VD-3** BP upstream count | Do three upstream relays per BP change the answer? Two is the current fixture; SPO practice is two public plus one unlisted. | tooling ready, not run | [how to run](../vote-diffusion-study.md#block-producer-upstream-count) |
| **VD-4** committee scale | What burst does a network with ~1000 block producers produce? | not started | — |
| **VD-5** offer cap | Does capping *announcement* fanout give pull's byte count with bounded push's peak? | not started | — |
| **VD-6** seed replication | Does the VD-2 BP-protection result hold across seeds? | not started | — |

VD-3 and VD-4 were requested in the 2026-09-22 working session. VD-5 follows from
the VD-2 finding below. VD-6 exists because VD-2 is a single seed and is currently
the basis of a recommendation.

## What is settled

**Arrival time is not the deciding variable.** Every arm reaches quorum between
3.10s and 3.85s from `t0`, against a 7.000s voting deadline and a 14.000s
certificate-inclusion boundary. The gate at 3.000s accounts for most of that
number. The part that a transport choice actually moves is 0.334s (`push-all`)
versus 0.850s (`pull-offer-all`), out of a 4.000s allowance. See
[time-budget.md](time-budget.md).

**Peak bandwidth separates the arms, not total bytes.** At 1500 nodes, relay
peak sent in a one-second window:

| Arm | Wire GB | Median relay peak | Max relay peak | Q95 from t0 |
|---|---:|---:|---:|---:|
| `push-all` | 32.68 | 10.29 Mbit/s | 60.65 Mbit/s | 3.334s |
| `push-cap-22-bp` | 19.62 | 7.31 | 7.31 | 3.335s |
| `push-cap-8-bp` | 7.38 | 2.66 | 2.66 | 3.345s |
| `pull-offer-all` 8/8 | 4.15 | 1.26 | 9.14 | 3.850s |
| `pull-offer-all` 40/40 | 15.72 | 4.92 | 28.80 | 3.850s |
| `pull-offer-all` 64/64 | 24.39 | 7.61 | 43.55 | 3.850s |

Bounded push has a flat profile — every relay forwards exactly `k` copies, so
median equals max. Pull keeps a 7x tail because announcements still reach every
peer. `push-cap-8-bp` has a **lower peak than pull at every tested control size**
and arrives 0.5s earlier, at 1.8x pull's total bytes.

**Pull does not remove copies; it shrinks them.** Pull sends 348.1M announcements,
against 347.7M bodies for `push-all` — the same flood, one message class down. A
vote body is 94 bytes, so an 8-byte announcement is a 11.8x saving per copy and a
64-byte announcement is only 1.5x. That is the whole of pull's advantage:

| Pull announce/request bytes | Bodies GB | Announcements GB | Requests GB | Total | vs `push-all` |
|---|---:|---:|---:|---:|---:|
| 8/8 | 1.26 | 2.78 | 0.11 | 4.15 | 7.88x less |
| 40/40 | 1.26 | 13.92 | 0.54 | 15.72 | 2.08x less |
| 64/64 | 1.26 | 22.28 | 0.86 | 24.39 | 1.34x less |

Bodies are 30% of pull's traffic at 8/8 and 5% at 64/64. **The lever is the
announcement fanout, not the body fanout** — which is what VD-5 tests, and what
a rate-limited push/pull hybrid should cap first. Applying VD-2's cap-8 copy
ratio (21.7% of consumers) to the announcement flood estimates ~1.97 GB at 8/8,
below pull and below `push-cap-8-bp`. That is an extrapolation, not a run.

**Bounded push must protect BP links.** Without protection, caps 22/16/8 reach
quorum at 0/26 EBs: the hash-ranked subset can omit the block producers that
need the votes. Marking each BP's upstream links `always-forward-votes`, within
the same total cap, restores 20/26 and the full endorsement count at all three
caps. One seed — see VD-6.

## What is not settled

No adversary is modeled in any arm. An honest-network result cannot say how hard
it is to slow pull down by withholding or delaying offers, which is the question
that decides whether the 0.5s gap is real under attack. See
[model-gaps.md](model-gaps.md) for the rest.
