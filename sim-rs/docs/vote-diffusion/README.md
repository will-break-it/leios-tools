# Vote diffusion

How should Linear Leios move vote bundles between nodes? Two strategies are on
the table:

- **Push** — when a node accepts a vote, it sends the body to every peer.
- **Pull** — it sends the 8-byte identifier to every peer, and sends the body to
  those that ask.

[transports.md](transports.md) states both rules exactly. [time-budget.md](time-budget.md)
decomposes the timings. [model-gaps.md](model-gaps.md) says what these runs
cannot answer.

## The comparison

1500 nodes, 458 stake pools, seed 0, 400 slots, 8-byte announcements.

| | Pull | Push | |
|---|---:|---:|---|
| Total bytes, 2 relays per producer | 4.15 GB | 32.68 GB | pull 7.9x less |
| Busiest relay, one-second peak | 9.14 Mbit/s | 60.65 Mbit/s | pull 6.6x lower |
| Quorum at 2 relays per producer | 3.850s | 3.334s | pull +0.52s |
| Quorum at 3 relays per producer | 3.358s | 3.161s | **pull +0.20s** |

Votes cannot be cast before 3.000s, are due at 7.000s, and a certificate cannot
be included before 14.000s. Every arm finishes with over three seconds to spare,
so **the timing difference is not the deciding variable — the bandwidth is.**

Giving each producer a third upstream relay, which is common SPO practice,
shrinks pull's penalty from 0.52s to 0.20s. It helps because a node then has
three peers that might offer it a vote, so the request rule stops setting the
tail: pull's 95th-percentile arrival falls from 0.875s to 0.362s.

## The announcement size decides more than the strategy does

Pull does not send fewer messages. It sends **348.1M announcements** where push
sends **347.7M bodies** — the same flood, one message class down. A vote body is
94 bytes, so pull's entire advantage is the size ratio:

| Announcement / request bytes | Pull total | vs push |
|---|---:|---:|
| 8 / 8 | 4.15 GB | 7.9x less |
| 40 / 40 | 15.72 GB | 2.1x less |
| 64 / 64 | 24.39 GB | **1.3x less** |

At 64 bytes pull saves almost nothing. **How an announcement is encoded on the
wire matters more than which strategy is chosen**, and the 8-byte figure is a
modelling assumption, not a measured encoding. Settling that encoding is worth
more than any further transport simulation.

Bodies are only 30% of pull's traffic at 8 bytes and 5% at 64. They already
travel along a near-spanning tree with zero redundant arrivals, so there is
nothing left to save on the body path.

## Experiments

| Experiment | Question | Status |
|---|---|---|
| **Push vs pull** | Does vote streaming stay feasible at 750–1500 nodes, and how do the strategies compare? | done — 108 runs, seeds 0–2 |
| **Control size and per-node traffic** | How much does pull depend on the announcement size, and where does the load sit? | done — 10 runs, seed 0 |
| **Relays per producer** | Does a third upstream relay change the answer? | seed 0 done, seeds 1–2 running |
| **Publish vs receive** | Of that gain, how much is the producer publishing over three relays and how much is it receiving over three? | not started |
| **Committee scale** | What burst does a network with ~1000 block producers produce? | not started |
| **Serving limits** | Does offering to everyone but rate-limiting the *serving* side lower the peak without losing coverage? | needs simulator work |

Evidence: [push vs pull](../vote-diffusion-results-20260910/README.md) and
[control size and per-node traffic](../vote-diffusion-followup-20260915/README.md).
[How to run a matrix](../vote-diffusion-study.md).

## Ruled out

**Forwarding to a subset of peers.** Capping how many peers a node forwards to
saves bandwidth and loses certification: across 72 runs, a cap of 8 produced
zero certificates in every one, and caps of 16 and 8 never reached a quorum at
the median node. A node the subset misses never receives the vote, and enough
producers are missed that the rest cannot reach 75% of stake. The same applies
to capping announcements — no offer means no request. Offers have to reach
everyone; the bandwidth lever belongs on the serving side instead. The runs are
kept in the [push vs pull report](../vote-diffusion-results-20260910/README.md)
so the idea is not re-proposed, not because it is a candidate.

## Open questions

- **The announcement encoding**, above. It dominates the comparison.
- **The request policy.** A node asks the first peer that offered, with no
  timeout, no retry and no hedging. That is fine on an honest network and
  untested otherwise; adversarial behaviour is out of scope for this study.
- **Scale.** Everything here is 750 or 1500 nodes with 216 or 458 stake pools.
