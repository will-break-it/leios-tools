# Where the time goes

"Push reaches quorum half a second before pull" is true and almost entirely
uninformative on its own, because most of both numbers is a fixed wait that no
transport choice touches. This page decomposes it. All figures are VD-2:
1500 nodes, 458 stake pools, `top-stake-seats`, seed 0, 400 slots.

## The fixed timeline

Everything is measured from `t0`, the start of the slot of the ranking block
that announced the EB.

```
t0        t0+3.000s              t0+7.000s                    t0+14.000s
|─────────────|──────────────────────|─────────────────────────────|
  3 x L_hdr     L_vote = 4.000s        L_diff = 7.000s
  header         voting window          diffusion allowance
  diffusion      (votes due)            (certificate may be included)
              ^ gate: voting opens
```

A voter may not vote before the gate at 3.000s, and honest Linear nodes wait for
it. So a reported quorum time of 3.334s is **3.000s of gate plus 0.334s of
everything else**. Only that second part responds to the transport.

## Post-gate cost by arm

Only arms that actually attained the quorum appear here. The unprotected bounded
caps reached quorum on 0 of 26 EBs, so they have no meaningful time.

| Arm | Q0 | Q50 | **Q95** | Q95 from t0 | Margin to 7.000s deadline |
|---|---:|---:|---:|---:|---:|
| `push-all` | 0.097s | 0.112s | **0.334s** | 3.334s | +3.666s |
| `push-cap-22-bp` | 0.098s | 0.115s | **0.335s** | 3.335s | +3.665s |
| `push-cap-16-bp` | 0.100s | 0.117s | **0.338s** | 3.338s | +3.662s |
| `push-cap-8-bp` | 0.107s | 0.124s | **0.345s** | 3.345s | +3.655s |
| `pull-offer-all` 8/8 | 0.135s | 0.171s | **0.850s** | 3.850s | +3.150s |
| `pull-offer-all` 40/40 | 0.136s | 0.171s | **0.850s** | 3.850s | +3.150s |
| `pull-offer-all` 64/64 | 0.136s | 0.171s | **0.850s** | 3.850s | +3.150s |

Q0 is the first node anywhere, Q50 the stake-weighted median node, Q95 the
95th-percentile node by stake. Each is the moment that node's own tally crosses
75% of total active stake. Q95 is an availability quantile across nodes — it is
not "95% of the votes" and not a worst-case guarantee.

Three readings:

- **Pull costs 2.5x in the part that varies** (0.850s vs 0.334s), not 1.15x as
  the end-to-end numbers suggest.
- **Both consume at most 21% of the 4.000s voting window**, and the certificate
  cannot be included until 14.000s regardless. Neither arm is close to the
  binding constraint on an honest network.
- **Bounding push is nearly free in time**: cap 8 with BP protection costs 0.011s
  over unrestricted push, while cutting peak relay bandwidth from 60.65 to
  2.66 Mbit/s.

## Why pull's tail is longer

Per-arrival delay, voter to receiving node, across every accepted arrival:

| Arm | Mean | p95 | Max | Arrivals |
|---|---:|---:|---:|---:|
| `push-all` | 0.171s | 0.511s | 1.238s | 347.7M |
| `push-cap-8-bp` | 0.189s | 0.556s | 1.402s | 78.5M |
| `pull-offer-all` 8/8 | 0.235s | 0.875s | 1.995s | 13.4M |

The extra round trip costs **+0.064s at the mean but +0.364s at p95 and +0.757s
at the max**. Quorum at a well-connected node needs only the fast arrivals, so
Q0 and Q50 barely move (+0.038s, +0.059s). Q95 is set by the nodes on the long
paths, where the announce/request exchange is paid at every hop and the delays
compound — hence 0.850s.

That is also why the bounded push arms hold their timing: fewer copies raises
mean arrival delay slightly (0.171s to 0.189s) but adds no round trip, so the
tail does not stretch.

## What does not move the timing

Control-message size changes pull's bytes by 5.9x and its peak bandwidth by
4.8x, and changes its quorum time **not at all** (0.850s at 8, 40 and 64 bytes).
Links are 10 Mbit/s each and the busiest relay peaks at 43.55 Mbit/s summed
across ~37 links, so no link is saturated in any arm. Timing here is propagation
and hop count, not congestion. A scenario that does saturate links — VD-4's
larger committee, or a protocol burst — would not behave this way.

## Reading caveats

- Times are means over the EBs that attained the quorum (20 of 26). The fixed
  400-slot cutoff leaves the newest EBs unfinished. Equal counts across arms do
  not prove the same EBs.
- Send timestamps mean queued for transmission; receive timestamps mean delivered.
- One seed, one topology, one committee mode. VD-6 is the replication.
- No adversary. See [model-gaps.md](model-gaps.md) — an honest-network tail is
  not a bound on an attacked one, and the request rule is the part an adversary
  would target.
