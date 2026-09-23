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
| **VD-3** BP upstream count | Do three upstream relays per BP change the answer? Two is the current fixture; SPO practice is two public plus one unlisted. | seed 0 done, seeds 1–2 running | [how to run](../vote-diffusion-study.md#block-producer-upstream-count) |
| **VD-3b** upstream direction | Of VD-3's gain, how much is the producer *publishing* over three relays and how much is it *receiving* over three? | not started | — |
| **VD-4** committee scale | What burst does a network with ~1000 block producers produce? | not started | — |
| **VD-5** serving limits | Does offering to everyone and rate-limiting the *serving* side keep pull's coverage at a lower peak? | needs the serving limit implemented | — |
| **VD-6** ~~bounded-fanout replication~~ | Withdrawn: it would replicate a result for a direction the evidence rules out. See [Bounded fanout is not a direction](#bounded-fanout-is-not-a-direction). | withdrawn | — |

VD-3 and VD-4 were requested in the 2026-09-22 working session. VD-3b separates
the two effects VD-3 changes at once. VD-5 is the hybrid that session converged
on.

**Adversarial behaviour is out of scope for this study.** Extending the simulator
to model withholding, grinding or equivocating peers is more work than the
question justifies for now. [model-gaps.md](model-gaps.md) records what that
leaves unanswered, so no result here is read as covering it.

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

Bodies are 30% of pull's traffic at 8/8 and 5% at 64/64, so the offer flood is
where the bytes are. **Capping that flood is not the answer** — see
[Bounded fanout is not a direction](#bounded-fanout-is-not-a-direction): a node
that receives no offer sends no request, so coverage breaks exactly as it does
for capped bodies. An earlier revision of this page proposed capping
announcements and estimated ~1.97 GB at 8/8; that is withdrawn, because it
describes a rule the capped-fanout runs predict would fail.

The honest levers are aggregating offers so one message carries several
identifiers, and rate-limiting the **serving** side rather than the offering
side. Pull already moves bodies along a near-spanning tree with zero redundant
arrivals, so there is nothing left to save there.

**Bounded fanout is not a direction.** Across VD-1's 72 capped runs — two network
sizes, two committee modes, three seeds, both duplicate orders — forwarding to a
subset destroys certification:

| Transport | Cap | EBs | Q50 | Q95 | L1 endorsements |
|---|---|---:|---:|---:|---:|
| `push-all` | none | 258 | 200 | 200 | 99 |
| `pull-offer-all` | none | 258 | 200 | 200 | 99 |
| `push-cap-22` | 22 | 258 | 197 | **0** | 84 |
| `push-cap-16` | 16 | 258 | **0** | **0** | 18 |
| `push-cap-8` | 8 | 258 | **0** | **0** | **0** |

Cap 8 produced **zero certificates in all 24 of its runs**. A node the selection
subgraph misses never receives the vote, and enough producers are missed that
the remainder cannot reach 75% of stake. This costs liveness and throughput
rather than safety — a node holding a certificate can still include it — but it
is a total loss of certification, not a trim.

`push-cap-N-bp` restores it (VD-2, one seed) only because `always-forward-votes`
marks producer links out of band. That is a topology annotation, not a protocol
mechanism: a node would have to learn which of its downstream peers are block
producers, and nothing stops a peer claiming to be one. Treat the capped arms as
a **negative result worth keeping**, not a design to tune.

## What is not settled

No adversary is modeled in any arm, and none will be — simulating one is out of
scope. An honest-network result cannot say how hard it is to slow pull down by
withholding or delaying offers. That gap is recorded rather than closed, and it
carries more weight now that VD-3 has narrowed pull's timing penalty: the case
for pull increasingly rests on a request policy whose behaviour under a hostile
peer is untested. See [model-gaps.md](model-gaps.md) for the rest.
