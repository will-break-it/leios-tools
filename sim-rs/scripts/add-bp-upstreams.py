#!/usr/bin/env python3
"""Give every block producer a target number of upstream relays.

The study fixtures give each BP two upstream relays. SPO practice is commonly
two public relays plus a third that is not registered on chain, so the vote
diffusion matrix needs a three-upstream variant.

Deriving that variant from an existing topology, rather than generating a fresh
one, keeps every other property identical -- locations, stake, relay graph,
latencies, bandwidth, core counts -- so a comparison against the two-upstream
runs isolates the upstream count. Generating a new topology would change the
whole graph at once.

Links are added in both directions, matching how the fixtures already connect a
BP to its relays: the BP lists the relay under `producers` and the relay lists
the BP back. A BP publishes its own votes to the same relays it consumes from.

Latency for a new link is sampled from the source topology's own
distance-to-latency pool, the same rule `generate-topology.py` uses, so added
links are drawn from the measured distribution rather than invented. The
fixture's existing BP links are all about 0.2 ms because each producer sits
beside its two relays; a third relay that is somebody else's, or the operator's
own in another region, is not in that rack. `--latency copy` models the
co-located case instead, and the two are worth running against each other before
reading much into the result.
"""

import argparse
import collections
import importlib.util
import json
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def load_generator():
    """Reuse haversine_km and sample_latency without duplicating them."""
    spec = importlib.util.spec_from_file_location('gen', HERE / 'generate-topology.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def relays_and_producers(nodes):
    relays = [name for name, node in nodes.items() if not node.get('stake', 0)]
    producers = [name for name, node in nodes.items() if node.get('stake', 0)]
    return relays, producers


def choose(gen, nodes, bp, relays, taken, strategy, rng, load):
    """Pick one relay for `bp` that is not already an upstream.

    Least-loaded first, then by the strategy. Plain nearest-relay selection
    concentrates: on the 1500-node fixture it put 105 producers behind a single
    relay, which a bounded protected fanout cannot serve -- the runner rejects a
    node with more protected consumers than the cap, and a hub that large would
    also dominate the result for reasons unrelated to the upstream count.
    Balancing spreads the added links one per relay while they last.
    """
    candidates = [r for r in relays if r not in taken]
    if not candidates:
        raise ValueError(f'{bp}: no relay left to add as an upstream')
    fewest = min(load[r] for r in candidates)
    candidates = [r for r in candidates if load[r] == fewest]
    if strategy == 'random':
        return rng.choice(sorted(candidates))
    lon, lat = nodes[bp]['location']
    return min(candidates, key=lambda r: (
        gen.haversine_km(lon, lat, *nodes[r]['location']), r))


def add_upstreams(topology, target, strategy='nearest', seed=0, latency='sampled'):
    gen = load_generator()
    source = gen.analyze_source(topology)
    nodes = topology['nodes']
    relays, producers = relays_and_producers(nodes)
    if not producers:
        raise ValueError('Topology has no stake-holding nodes')
    rng = random.Random(seed)
    # Existing upstream links count towards the balance, so the added ones go
    # to relays that are not already serving producers wherever possible.
    load = collections.Counter(
        relay for name in producers for relay in nodes[name].get('producers', {}))
    added = 0
    for bp in producers:
        peers = nodes[bp].setdefault('producers', {})
        if any(nodes[p].get('stake', 0) for p in peers):
            raise ValueError(f'{bp}: already has a stake-holding upstream')
        if len(peers) > target:
            raise ValueError(f'{bp}: has {len(peers)} upstreams, more than the target {target}')
        # Copy the link settings the BP already uses, so the added link is not
        # the only one on the node with different bandwidth.
        template = dict(next(iter(peers.values()))) if peers else {}
        while len(peers) < target:
            relay = choose(gen, nodes, bp, relays, peers, strategy, rng, load)
            load[relay] += 1
            lon, lat = nodes[bp]['location']
            distance = gen.haversine_km(lon, lat, *nodes[relay]['location'])
            link = dict(template)
            if latency == 'sampled':
                link['latency-ms'] = round(gen.sample_latency(source, distance, rng), 4)
            elif not template:
                raise ValueError(f'{bp}: --latency copy needs an existing link to copy')
            peers[relay] = link
            # Reciprocal, matching the fixtures: the relay serves the BP and
            # the BP publishes to it.
            back = dict(link)
            nodes[relay].setdefault('producers', {})[bp] = back
            added += 1
    return added


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('source', type=Path)
    parser.add_argument('destination', type=Path)
    parser.add_argument('--upstreams', type=int, required=True,
                        help='Target upstream relay count per block producer')
    parser.add_argument('--strategy', choices=['nearest', 'random'], default='nearest',
                        help="'nearest' models a relay near the producer; "
                             "'random' models an unlisted relay anywhere")
    parser.add_argument('--latency', choices=['sampled', 'copy'], default='sampled',
                        help="'sampled' draws from the source topology's own "
                             'distance-to-latency pool, modelling a third relay that is '
                             "not in the producer's rack; 'copy' reuses the producer's "
                             'existing link latency, modelling a co-located private relay')
    parser.add_argument('--seed', type=int, default=0,
                        help='Seed for latency sampling and for --strategy random')
    args = parser.parse_args()
    if args.upstreams < 1:
        parser.error('--upstreams must be positive')
    if args.destination.exists():
        parser.error(f'{args.destination} already exists')
    topology = json.loads(args.source.read_text())
    added = add_upstreams(topology, args.upstreams, args.strategy, args.seed, args.latency)
    nodes = topology['nodes']
    relays, producers = relays_and_producers(nodes)
    args.destination.write_text(json.dumps(topology))
    serving = collections.Counter(
        relay for name in producers for relay in nodes[name]['producers'])
    print(f'{len(nodes)} nodes, {len(producers)} producers, {len(relays)} relays; '
          f'added {added} link(s) so every producer has {args.upstreams} upstream relay(s). '
          f'Busiest relay now serves {max(serving.values())} producer(s); '
          f'a bounded protected fanout must be at least that large.',
          file=sys.stderr)


if __name__ == '__main__':
    main()
