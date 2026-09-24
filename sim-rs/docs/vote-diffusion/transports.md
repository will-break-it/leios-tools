# Vote transport rules

Each strategy is one forwarding rule, stated in full, with the configuration
that produces it. The first two are the live candidates; the bounded rules after
them were tested and [ruled out](README.md#ruled-out), and are kept here so the
archived runs remain readable.

A node runs the rule once per vote bundle, at the moment it first accepts that
bundle. `consumers` are its downstream peers in the topology. The peer a bundle
arrived from is excluded unless `vote-transport-echo-to-source` is set, which is
false in every published run.

## `push-all`

> On first acceptance, send the **body** to every consumer except the source.

```yaml
vote-transport: "push"
vote-push-fanout: null
```

Unrestricted. This is the arm the prototype implements today.

## `pull-offer-all`

> On first acceptance, send an **announcement** (the bundle identifier) to every
> consumer except the source. A node receiving an announcement for a bundle it
> does not hold sends a **request** to the first peer that offered it, and that
> peer replies with the body.

```yaml
vote-transport: "announce-then-request"
vote-announcement-size-bytes: 8     # also run at 40 and 64
vote-request-size-bytes: 8          # also run at 40 and 64
relay-strategy: "request-from-first"
```

Announcements are not capped: the offer floods the mesh exactly as `push-all`
floods bodies. Bodies follow the request graph, which is a spanning tree here —
8,927 bundles x 1,499 other nodes, zero redundant arrivals. Requests are served
unconditionally; there is no per-peer serving limit and no hedging.

`relay-strategy: "request-from-all"` exists and would request from every offerer,
but it is a **global** setting that also governs EB and transaction fetching, so
it is not a vote-only multiplicity knob. A vote-scoped one does not exist yet.

The 8-byte announcement and request are a modelling assumption covering the
identifier plus application framing, excluding TCP/IP. 40 and 64 bytes are
sensitivity points, not verified wire encodings.

Run-name token: `announce-then-request`, plus `a8-r8` / `a40-r40` / `a64-r64`.

## Ruled out: bounded fanout

The three rules below cap how many peers a node forwards to. They save bandwidth
and lose certification — see [Ruled out](README.md#ruled-out). They are not
candidates; this section documents what the archived arms did.

### `push-cap-N`

> On first acceptance, send the **body** to `N` consumers, chosen by ranking every
> eligible consumer on `hash(seed, this node, bundle id, peer)` and taking the
> lowest `N`.

```yaml
vote-transport: "push"
vote-push-fanout: N            # 22, 16 and 8 were tested
vote-push-fanout-protects-producers: false
```

The selection is keyed on the bundle, so **each vote takes its own subgraph**.
It is a pure function of the seed: identical across runs, platforms and shard
layouts, and independent of arrival order. There is no repair mechanism and no
delivery guarantee — a node that no selected path reaches never gets that vote.
`N` bounds how many copies *one node relays*, not how many copies of a vote
cross the network.

Run-name token: `f22`, `f16`, `f8`; `fall` for `push-all`.

### `push-cap-N-bp`

> As `push-cap-N`, but consumers reached over a link marked
> `always-forward-votes: true` are ranked first and take their places **inside
> the same total cap `N`**.

```yaml
vote-transport: "push"
vote-push-fanout: N
vote-push-fanout-protects-producers: true
```

A relay protecting one BP at cap 22 has 21 places left for other consumers. The
protected arm gets no extra copy — this compares *which* recipients a fixed
budget buys. The study runner marks each BP's upstream relay links in the saved
topology; routing reads those markers, not stake. A node with more protected
consumers than the cap is rejected.

Run-name token: `bptrue` (`bpfalse` otherwise).

## Duplicate handling: `push` vs `push-late-dedupe`

Orthogonal to the rules above, and about *when a node records a vote as seen*,
never about when it sends one.

| Setting | Behaviour |
|---|---|
| `push` | Mark the bundle id seen **on arrival**. Copies arriving while the first verification is still pending are dropped. |
| `push-late-dedupe` | Mark it seen **after verification completes**. Copies arriving during that window each trigger their own verification. |

Both discard copies of an already verified bundle. The inspected Haskell
prototype records a vote as known only after verification, so it behaves like
`push-late-dedupe`. The 108-run study covers both; the later follow-up uses
`push` only, so its conclusions carry no claim about verification load under the
prototype's order.

## Run-name grammar

```
<nodes>-<committee>-<transport>-f<fanout>-bp<protect>-a<announce>-r<request>-s<seed>
1500  -top-stake-seats-push      -f8      -bptrue    -a8       -r8      -s0
```

Unlimited push and pull both record `bpfalse`, because no bounded selection
applies to either.
