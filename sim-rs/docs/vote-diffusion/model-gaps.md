# What these runs do not model

Every number in these studies comes from an honest network with no flow control
and no request timeouts. This page states each gap and what it disqualifies, so
a reader can tell which conclusions survive it.

## 1. No adversary, anywhere

No arm includes a node that withholds, delays, equivocates or floods, and none
is planned: extending the simulator to model one is more work than this study
justifies. This section therefore records a standing limitation, not a backlog
item.

The gap bites hardest on `pull-offer-all`, because its request rule has no
recovery path. In [`receive_announce_votes`](../../sim-core/src/sim/linear_leios.rs),
a node that receives an offer for a bundle it does not hold marks it `Requested`
and sends one request to **the first peer that offered it**. Subsequent offers
for the same bundle are then ignored. There is **no timeout, no retry and no
hedged second request**. On an honest network every peer serves, so this never
surfaces. Against a peer that offers first and never delivers, that node never
obtains the vote at all.

Consequences:

- **0.850s is an honest-network figure**, not a bound. The measured pull latency
  says nothing about pull under a grinding or withholding adversary, and the
  0.5s gap to push cannot be traded against attack resistance on this evidence.
- **Any pull or hybrid design needs a request policy this study has not tested**:
  timeout, retry, hedging across several upstreams, or serving limits. Until
  those are measured, pull's timing figure is conditional on a policy nobody has
  specified.
- Push has no equivalent dependency — a pushed body needs no cooperation from
  the receiver's chosen peer — but bounded push has its own failure mode, below.

Failing to diffuse votes costs liveness (lost throughput), not safety: a node
holding a valid certificate can still include it. That is why this gap was
accepted for the first pass, not why it is closed.

## 2. Bounded fanout has no repair mechanism, and loses certification

`push-cap-N` picks recipients by `hash(seed, node, bundle, peer)`. Each vote
takes its own subgraph, and **delivery to any particular node is not guaranteed**.
Nothing detects or repairs a node the selection skipped. Across 72 capped runs
this was not a partial loss: a cap of 8 produced **zero L1 endorsements in every
run**, and caps of 16 and 8 never reached Q50. The same objection applies to capping
announcement fanout — no offer means no request — so a bounded-coverage rule is
ruled out on either message class, and the bandwidth lever belongs on the
serving side instead.

Protection is a topology marking, not a protocol mechanism: the study runner sets
`always-forward-votes: true` on each BP's upstream links. A real deployment would
need the node to learn which of its downstreams are block producers, which is
information an adversary may be able to claim falsely.

## 3. CPU is a cost model, not execution

Vote verification is charged at `vote-validation-cpu-time-ms: 2.9` against 4
cores per node. No BLS runs. That cost model is what makes the duplicate-handling
order matter:

| Order | Completed verifications per accepted arrival |
|---|---:|
| `push` (mark seen on arrival) | 1.00 |
| `push-late-dedupe` (mark seen after verification) | **9.69** |

The inspected Haskell prototype uses the second order. **The control-size
follow-up runs only the first**, so its findings carry no claim about
verification load in the prototype. The 108-run study covers both and found the
second order costs 0.46s of Q95 time at 1500 nodes and reduces endorsements in
the everyone-votes arm.

## 4. No flow control or per-peer serialization

The simulator has no notification credits, no per-peer serial handler and no
multiplexer. The prototype processes votes serially per peer and shares outgoing
notification capacity with other messages, **dropping votes when no credit is
available**. Those mechanisms change which duplicates reach verification at all.

The peak-bandwidth numbers are also modeled vote-protocol bytes only: no TCP/IP
framing, no other mini-protocols competing for the same egress, and no egress
scheduler. A node-wide peak sums all outgoing links; the 10 Mbit/s limit is
per link.

## 5. The header path is approximated

The simulator models a ranking-header identifier announce/request/body exchange
with a flat `leios-header-diffusion-time-ms: 1000`. The node validates full Leios
header announcements before forwarding and has a separate ChainSync path. This
approximation **does not cancel between arms**: verification load changes CPU
queueing, which changes header eligibility, which changes how many votes get
cast. Quantitative certification or backlog claims should not be carried to the
node without re-checking this.

## 6. Scope of the current evidence

| | Push vs pull | Control size |
|---|---|---|
| Seeds | 0, 1, 2 | **0 only** |
| Nodes | 750, 1500 | 1500 |
| Committee | everyone, top-stake-seats | top-stake-seats |
| Duplicate order | both | `push` only |
| BP upstreams | 2 | 2 |
| Per-node traffic | no (network totals) | yes, all 1500 nodes |

The three-relay comparison is one seed so far; seeds 1 and 2 are running.
Timing means are conditional on attainment and cover 20 of 26 EBs; the 400-slot cutoff leaves the newest EBs
unfinished, and equal attainment counts across arms do not prove the same EBs.

## What the evidence does support

Stated narrowly, so the claims can be checked:

1. On an honest 1500-node network with these parameters, **no transport choice
   comes close to the 7.000s voting deadline**; the spread is 0.334s to 0.850s
   inside a 4.000s window.
2. **Peak relay bandwidth differs 6.6x between the two strategies** (9.14
   against 60.65 Mbit/s) while arrival time differs by 0.5s, or 0.2s with a
   third upstream relay. Bandwidth is the axis worth optimizing.
3. **Pull's advantage is entirely the size ratio between an announcement and a
   94-byte body**, and disappears as announcements grow. Its copy count equals
   unrestricted push's.
4. **Bounded fanout loses certification**, on either message class.

Nothing here supports a claim about the Haskell node's throughput, about
behaviour under attack, or about a pull design with a request policy that has
not been simulated.
