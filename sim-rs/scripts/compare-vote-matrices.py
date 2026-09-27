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
rounded figure in the run log, `wire_gb_exact` reads `false`, and the peak
columns read `n/a`, because a peak cannot be recovered from network totals. A
matrix that has captures but no checksum manifest is an error, not a matrix
without captures.
"""

import argparse
import csv
import hashlib
import importlib.util
import json
import statistics
import subprocess
import sys
import tempfile
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

# One list, so a column and its heading cannot drift apart.
SCHEMA = [
    ('matrix', 'Matrix'), ('seed', 'Seed'), ('nodes', 'Nodes'),
    ('bp_upstreams', 'Upstreams'), ('upstream_latency', 'Upstream latency'),
    ('transport', 'Transport'), ('cap', 'Cap'), ('protect_bp', 'Protect BP'),
    ('announce_request_bytes', 'Announce/request B'), ('ebs', 'EBs'),
    ('q50', 'Q50'), ('q75', 'Q75'), ('q95', 'Q95'),
    ('q95_by_deadline', 'Q95 by deadline'), ('q75_mean_s', 'Q75 mean s'),
    ('q95_mean_s', 'Q95 mean s'), ('endorsements', 'Endorsements'),
    ('wire_gb', 'Wire GB'), ('wire_gb_exact', 'Wire GB exact'),
    ('relay_median_peak_mbit_s', 'Relay median peak Mbit/s'),
    ('relay_max_peak_mbit_s', 'Relay max peak Mbit/s'),
    ('bp_max_peak_mbit_s', 'BP max peak Mbit/s'),
]
COLUMNS = [key for key, _ in SCHEMA]
HEADINGS = [heading for _, heading in SCHEMA]


def fmt(value, digits=3):
    return 'n/a' if value is None else f'{value:.{digits}f}'


def verify(root, manifest):
    path = root / manifest
    if not path.is_file():
        # Captures are optional, a lost manifest is not: without it the peak
        # columns would silently read n/a on a matrix that did capture them.
        present = sorted(p.name for p in root.glob('*.vote-traffic.json'))
        if present:
            raise ValueError(
                f'{root}: {len(present)} capture(s) present but {manifest} is missing')
        return {}
    checksums = json.loads(path.read_text())
    for name, expected in checksums.items():
        with (root / name).open('rb') as stream:
            if hashlib.file_digest(stream, 'sha256').hexdigest() != expected:
                raise ValueError(f'Checksum mismatch: {root / name}')
    return checksums


def peaks(root, run, captures, topologies):
    """Per-role peak rates, or None when the matrix captured no per-node traffic."""
    filename = run['run'] + '.vote-traffic.json'
    if filename not in captures:
        if (root / filename).is_file():
            raise ValueError(f'Capture missing from checksum manifest: {filename}')
        return None
    report = traffic.load(root / filename)
    if report['seed'] != int(run['seed']):
        raise ValueError(f"Capture seed differs from runs.csv: {run['run']}")
    duration = int(run['slots'])
    nodes = traffic.summarize(report, duration)
    size = run['nodes']
    if size not in topologies:
        topologies[size] = set(
            json.loads((root / f'topology-{size}.yaml').read_text())['nodes'])
    if {row['name'] for row in nodes} != topologies[size]:
        raise ValueError(f"Capture nodes differ from topology: {run['run']}")
    traffic.reconcile(nodes, (root / (run['run'] + '.txt')).read_text(), duration)
    result = {'total_sent_bytes': sum(row['sent_bytes'] for row in nodes)}
    for role in ['BP', 'relay']:
        subset = [row['sent_peak_1s_mbit_s'] for row in nodes if row['role'] == role]
        result[role] = {'median': statistics.median(subset), 'max': max(subset)} if subset else None
    return result


def extract(root):
    """Run the protocol extractor without writing into the matrix directory.

    The extractor saves results.json and RESULTS.md beside its inputs. Comparing
    is a read; mirroring the directory as symlinks keeps a published, checksummed
    run directory untouched and lets the comparator read a read-only mount.
    """
    with tempfile.TemporaryDirectory() as mirror:
        target = Path(mirror)
        for entry in root.iterdir():
            (target / entry.name).symlink_to(entry)
        done = subprocess.run([sys.executable, str(EXTRACTOR), str(target)])
        if done.returncode:
            # The extractor exits nonzero for a parse failure or any run that
            # did not pass, so say which matrix rather than surfacing a bare
            # CalledProcessError from a temporary path the caller never named.
            raise ValueError(f'{root}: the protocol extractor rejected this matrix')
        return json.loads((target / 'results.json').read_text())


def collect(label, root):
    extracted = extract(root)
    results = {r['run']: r for r in extracted['results']}
    with (root / 'runs.csv').open() as stream:
        runs = list(csv.DictReader(stream))
    captures = verify(root, 'vote-traffic-sha256.json')
    topologies = {}
    rows = []
    for run in runs:
        if run['status'] != 'passed':
            raise ValueError(f"{label}: {run['run']} is {run['status']}, not a result")
        protocol = results[run['run']]
        measured = peaks(root, run, captures, topologies)
        q75, q95 = protocol.get('quorum_q75'), protocol['quorum_p95']
        rows.append({
            'matrix': label,
            'seed': protocol['seed'],
            'nodes': protocol['nodes'],
            # Absent in CSVs written before the knob existed, which were all two.
            'bp_upstreams': run.get('bp_upstreams') or '2',
            # Absent in CSVs written before the knob existed, which all sampled.
            'upstream_latency': run.get('bp_upstream_latency') or 'sampled',
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
            # One numeric type in the column; the provenance rides beside it,
            # so the CSV stays parseable when a matrix captured no traffic.
            'wire_gb': (f"{measured['total_sent_bytes'] / 1e9:.6f}" if measured
                        else f"{protocol['wire_mb_rounded'] / 1000:.6f}"),
            'wire_gb_exact': 'true' if measured else 'false',
            'relay_median_peak_mbit_s': fmt(measured['relay']['median']) if measured and measured['relay'] else 'n/a',
            'relay_max_peak_mbit_s': fmt(measured['relay']['max']) if measured and measured['relay'] else 'n/a',
            'bp_max_peak_mbit_s': fmt(measured['BP']['max']) if measured and measured['BP'] else 'n/a',
        })
    return rows


def markdown(rows):
    lines = ['# Vote diffusion matrix comparison', '',
             'Wire GB is exact when the matrix captured per-node traffic and the rounded '
             'figure from the run log otherwise; the Wire GB exact column says which. ',
             '',
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
