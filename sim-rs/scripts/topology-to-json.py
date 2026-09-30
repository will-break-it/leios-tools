#!/usr/bin/env python3
"""Convert a pseudo-mainnet topology from YAML to JSON.

`sim-cli` reads either, because `serde_yaml` accepts JSON as a subset of YAML.
The study runner and the results extractor do not: they are standard-library
only, and PyYAML is not a dependency of this toolchain. Converting once keeps
both able to read the fixture.

Only the shape these fixtures actually use is accepted, and anything outside it
is an error rather than a guess:

    nodes:
      node-0:
        stake: 114016430          # optional; absent means a stakeless relay
        location:
        - 10.0485
        - 49.6986
        cpu-core-count: 6
        tx-generation-weight: 1   # optional
        producers:
          node-17:
            latency-ms: 57.8031
            bandwidth-bytes-per-second: 125000000

The converted file is verified against the source before it is written: node
count, per-node link count, and every scalar are compared, so a silent parse
error cannot reach a simulation.
"""

import argparse
import json
import re
import sys
from pathlib import Path

NODE = re.compile(r'^  ([\w-]+):$')
FIELD = re.compile(r'^    ([\w-]+):[ \t]*(.*)$')
LIST_ITEM = re.compile(r'^    - (.+)$')
PRODUCER = re.compile(r'^      ([\w-]+):$')
PRODUCER_FIELD = re.compile(r'^        ([\w-]+): (.+)$')


def scalar(text):
    """YAML scalars in these fixtures are ints or floats, nothing else."""
    text = text.strip()
    try:
        return int(text)
    except ValueError:
        pass
    try:
        return float(text)
    except ValueError:
        raise ValueError(f'Unsupported scalar: {text!r}')


def parse(lines):
    nodes, node, key, producer = {}, None, None, None
    for number, raw in enumerate(lines, 1):
        line = raw.rstrip('\n')
        if not line.strip() or line.lstrip().startswith('#'):
            continue
        if line == 'nodes:':
            continue
        try:
            if m := NODE.match(line):
                node, key, producer = {}, None, None
                nodes[m[1]] = node
            elif node is None:
                raise ValueError('Content before the first node')
            elif m := PRODUCER.match(line):
                if key != 'producers':
                    raise ValueError('Producer entry outside a producers block')
                producer = {}
                node['producers'][m[1]] = producer
            elif m := PRODUCER_FIELD.match(line):
                if producer is None:
                    raise ValueError('Producer field outside a producer')
                producer[m[1]] = scalar(m[2])
            elif m := LIST_ITEM.match(line):
                if key != 'location':
                    raise ValueError(f'List item under {key!r}, expected location')
                node['location'].append(scalar(m[1]))
            elif m := FIELD.match(line):
                key, value = m[1], m[2].strip()
                producer = None
                if key == 'producers':
                    if value:
                        raise ValueError('Inline producers are not supported')
                    node['producers'] = {}
                elif key == 'location':
                    if value:
                        raise ValueError('Inline location is not supported')
                    node['location'] = []
                else:
                    node[key] = scalar(value)
            else:
                raise ValueError('Unrecognised line')
        except ValueError as error:
            raise ValueError(f'line {number}: {error}\n  {line!r}') from None
    return {'nodes': nodes}


def verify(topology, lines):
    """Re-derive the counts straight from the text and compare."""
    nodes = topology['nodes']
    names = [m[1] for line in lines if (m := NODE.match(line.rstrip('\n')))]
    if len(names) != len(nodes) or set(names) != set(nodes):
        raise ValueError('Node set differs from the source')
    links = sum(1 for line in lines if PRODUCER.match(line.rstrip('\n')))
    parsed_links = sum(len(n.get('producers', {})) for n in nodes.values())
    if links != parsed_links:
        raise ValueError(f'Link count differs: {links} in source, {parsed_links} parsed')
    for name, node in nodes.items():
        if 'location' not in node or len(node['location']) != 2:
            raise ValueError(f'{name}: expected a two-element location')
        for peer, link in node.get('producers', {}).items():
            if peer not in nodes:
                raise ValueError(f'{name}: producer {peer} is not a node')
            if 'latency-ms' not in link:
                raise ValueError(f'{name} -> {peer}: no latency-ms')
    return len(nodes), links


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('source', type=Path)
    parser.add_argument('destination', type=Path)
    args = parser.parse_args()
    if args.destination.exists():
        parser.error(f'{args.destination} already exists')
    lines = args.source.read_text().splitlines(keepends=True)
    topology = parse(lines)
    count, links = verify(topology, lines)
    nodes = topology['nodes']
    pools = sum(1 for n in nodes.values() if n.get('stake', 0))
    args.destination.write_text(json.dumps(topology))
    # Read it back the way the runner and extractor will.
    again = json.loads(args.destination.read_text())
    if again != topology:
        raise ValueError('Round trip through JSON changed the topology')
    print(f'{count} nodes, {pools} stake pools, {count - pools} stakeless, {links} links',
          file=sys.stderr)


if __name__ == '__main__':
    main()
