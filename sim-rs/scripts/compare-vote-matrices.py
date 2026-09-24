#!/usr/bin/env python3
"""Join several completed vote-diffusion matrices into one comparison table.

`summarize-vote-diffusion-followup.py` reports one fixed ten-case matrix. This
reads any number of completed study directories and puts their arms in a single
table, so a new matrix can be read against the ones it is meant to be compared
with instead of in isolation.

It applies the same checks as the focused summarizer -- frozen input and log
checksums through the protocol extractor, capture checksums, per-node
reconciliation against the final network totals -- but asserts nothing about
which configurations a matrix should contain.

Per-node captures are optional. Without them the byte total comes from the
rounded figure in the run log and the peak columns read `n/a`, because a peak
cannot be recovered from network totals.
"""

import argparse
import csv
import hashlib
import importlib.util
import json
import statistics
import subprocess
import sys
from pathlib import Path

sys.dont_write_bytecode = True
SCRIPTS = Path(__file__).resolve().parent
EXTRACTOR = SCRIPTS.parent / 'docs/vote-diffusion-results-20260910/extract-results.py'


def load_traffic():
    spec = importlib.util.spec_from_file_location('traffic', SCRIPTS / 'summarize-vote-traffic.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


traffic = load_traffic()

COLUMNS = ['matrix', 'seed', 'nodes', 'bp_upstreams', 'transport', 'cap', 'protect_bp',
           'announce_request_bytes', 'ebs', 'q50', 'q75', 'q95', 'q95_by_deadline',
           'q75_mean_s', 'q95_mean_s', 'endorsements', 'wire_gb',
           'relay_median_peak_mbit_s', 'relay_max_peak_mbit_s', 'bp_max_peak_mbit_s']

HEADINGS = ['Matrix', 'Seed', 'Nodes', 'Upstreams', 'Transport', 'Cap', 'Protect BP',
            'Announce/request B', 'EBs', 'Q50', 'Q75', 'Q95', 'Q95 by deadline',
            'Q75 mean s', 'Q95 mean s', 'Endorsements', 'Wire GB',
            'Relay median peak Mbit/s', 'Relay max peak Mbit/s', 'BP max peak Mbit/s']


def fmt(value, digits=3):
    return 'n/a' if value is None else f'{value:.{digits}f}'


def verify(root, manifest):
    path = root / manifest
    if not path.is_file():
        return {}
    checksums = json.loads(path.read_text())
    for name, expected in checksums.items():
        with (root / name).open('rb') as stream:
            if hashlib.file_digest(stream, 'sha256').hexdigest() != expected:
                raise ValueError(f'Checksum mismatch: {root / name}')
    return checksums


def peaks(root, run, captures):
    """Per-role peak rates, or None when the matrix captured no per-node traffic."""
    filename = run['run'] + '.vote-traffic.json'
    if filename not in captures:
        return None
    report = traffic.load(root / filename)
    if report['seed'] != int(run['seed']):
        raise ValueError(f"Capture seed differs from runs.csv: {run['run']}")
    duration = int(run['slots'])
    nodes = traffic.summarize(report, duration)
    topology = json.loads((root / f"topology-{run['nodes']}.yaml").read_text())['nodes']
    if {row['name'] for row in nodes} != set(topology):
        raise ValueError(f"Capture nodes differ from topology: {run['run']}")
    traffic.reconcile(nodes, (root / (run['run'] + '.txt')).read_text(), duration)
    result = {'total_sent_bytes': sum(row['sent_bytes'] for row in nodes)}
    for role in ['BP', 'relay']:
        subset = [row['sent_peak_1s_mbit_s'] for row in nodes if row['role'] == role]
        result[role] = {'median': statistics.median(subset), 'max': max(subset)} if subset else None
    return result


def collect(label, root):
    subprocess.run([sys.executable, str(EXTRACTOR), str(root)], check=True)
    extracted = json.loads((root / 'results.json').read_text())
    results = {r['run']: r for r in extracted['results']}
    with (root / 'runs.csv').open() as stream:
        runs = list(csv.DictReader(stream))
    captures = verify(root, 'vote-traffic-sha256.json')
    rows = []
    for run in runs:
        if run['status'] != 'passed':
            raise ValueError(f"{label}: {run['run']} is {run['status']}, not a result")
        protocol = results[run['run']]
        measured = peaks(root, run, captures)
        q75, q95 = protocol.get('quorum_q75'), protocol['quorum_p95']
        rows.append({
            'matrix': label,
            'seed': protocol['seed'],
            'nodes': protocol['nodes'],
            # Absent in CSVs written before the knob existed, which were all two.
            'bp_upstreams': run.get('bp_upstreams') or '2',
            'transport': protocol['transport'],
            'cap': protocol['fanout'],
            'protect_bp': protocol['protects_producers'],
            'announce_request_bytes': f"{protocol['announcement_bytes']}/{protocol['request_bytes']}",
            'ebs': protocol['ebs_generated'],
            'q50': f"{protocol['quorum_median']['reached']}/{protocol['ebs_generated']}",
            'q75': f"{q75['reached']}/{q75['total']}" if q75 else 'n/a',
            'q95': f"{q95['reached']}/{q95['total']}",
            'q95_by_deadline': f"{q95['by_vote_deadline']}/{q95['total']}",
            'q75_mean_s': fmt(q75['mean_s']) if q75 else 'n/a',
            'q95_mean_s': fmt(q95['mean_s']),
            'endorsements': protocol['l1_endorsements'],
            'wire_gb': (f"{measured['total_sent_bytes'] / 1e9:.6f}" if measured
                        else f"{protocol['wire_mb_rounded'] / 1000:.3f} (rounded)"),
            'relay_median_peak_mbit_s': fmt(measured['relay']['median']) if measured and measured['relay'] else 'n/a',
            'relay_max_peak_mbit_s': fmt(measured['relay']['max']) if measured and measured['relay'] else 'n/a',
            'bp_max_peak_mbit_s': fmt(measured['BP']['max']) if measured and measured['BP'] else 'n/a',
        })
    return rows


def markdown(rows):
    lines = ['# Vote diffusion matrix comparison', '',
             'Peaks are node totals across outgoing links in fixed one-second windows, counted '
             'when queued for transmission. They are neither instantaneous nor sliding-window '
             'link throughput, and the bandwidth limit applies to each link, not each node.',
             '',
             'Q50/Q75/Q95 are quorum availability at nodes holding that share of stake. The '
             'certificate threshold is 75% of total voting stake in every row; the quantile '
             'varies the observer, not the threshold. Timing means are conditional on '
             'attainment and may cover different EBs, so equal counts are not equal identities.',
             '', '| ' + ' | '.join(HEADINGS) + ' |',
             '|' + '---|' * len(HEADINGS)]
    for row in rows:
        lines.append('| ' + ' | '.join(str(row[column]) for column in COLUMNS) + ' |')
    return '\n'.join(lines) + '\n'


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('matrices', nargs='+',
                        help='Completed study directory, optionally as LABEL=path')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(argv)
    rows = []
    seen = set()
    for entry in args.matrices:
        label, _, path = entry.partition('=')
        if not path:
            label, path = Path(label).name, label
        if label in seen:
            raise ValueError(f'Duplicate matrix label: {label}')
        seen.add(label)
        rows.extend(collect(label, Path(path).resolve(strict=True)))
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / 'comparison.md').write_text(markdown(rows))
    with (args.output / 'comparison.csv').open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=COLUMNS, lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)
    print(f'{len(rows)} arm(s) from {len(seen)} matrix/matrices in {args.output}', file=sys.stderr)
    return 0


if __name__ == '__main__':
    sys.exit(main())
