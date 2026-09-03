#!/usr/bin/env bash
# Vote-transport study at 750 and 1500 nodes: every transport arm, one summary
# file per run, no trace output.
#
# usage: scripts/vote-diffusion-study.sh <study config.yaml> <output dir> [seed ...]
#
# Arms: the four vote transports plus push-fanout, which is push with
# vote-push-fanout set, the bounded-fanout proposal.
#
# <study config.yaml> is ouroboros-leios/analysis/sims/2026w18/experiments/config.yaml.
# Seeds default to 0.  Each run prints its whole summary to
# <output dir>/<size>-<arm>-s<seed>.txt; the figures quoted in the PR are the
# last occurrence of each summary line in that file.
#
# The 750-node network is data/simulation/pseudo-mainnet/topology-v2-cip.yaml
# as committed.  The 1500-node network is derived here from topology-v2-1500.yaml
# by setting every node to 4 cores and every link to 10 Mb/s, which is what the
# 750-node file already has, so the two sizes differ in size only.
#
# Runs are sequential.  A 750-node run takes about nine minutes and 5 GB, a
# 1500-node run about twenty minutes and 11 GB, on a 2024 laptop.  The sharded
# engine is bit-identical on a fixed seed, so the summaries can be diffed.
set -euo pipefail

here=$(cd "$(dirname "$0")/.." && pwd)
cfg=${1:?study config.yaml}
out=${2:?output dir}
shift 2
seeds=${*:-0}
mkdir -p "$out"

# Always rebuild: a stale binary silently ignores a transport it predates.
cargo build --release --manifest-path "$here/Cargo.toml" >/dev/null
bin=$here/target/release/sim-cli

topo750=$here/../data/simulation/pseudo-mainnet/topology-v2-cip.yaml
topo1500=$out/topology-v2-1500-4core-10mbps.yaml
python3 - "$here/../data/simulation/pseudo-mainnet/topology-v2-1500.yaml" "$topo1500" <<'PY'
import json, sys
d = json.load(open(sys.argv[1]))
for n in d['nodes'].values():
    n['cpu-core-count'] = 4
    for p in n.get('producers', {}).values():
        p['bandwidth-bytes-per-second'] = 1250000
json.dump(d, open(sys.argv[2], 'w'))
PY

for seed in $seeds; do
  printf 'committee-selection-algorithm: "everyone"\nquorum-weight-fraction: 0.75\nseed: %s\n' "$seed" > "$out/seed-$seed.yaml"
  for size in 750 1500; do
    topo=$topo750
    [ "$size" = 1500 ] && topo=$topo1500
    for arm in announce push push-late-dedupe push-echo push-fanout; do
      file=$out/$size-$arm-s$seed.txt
      if "$bin" "$topo" -s 400 \
          -p "$cfg" \
          -p "$here/parameters/study-linear-tx-load.yaml" \
          -p "$here/parameters/turbo.yaml" \
          -p "$out/seed-$seed.yaml" \
          -p "$here/parameters/vote-$arm.yaml" > "$file" 2>&1; then
        echo "$size $arm seed $seed: $(grep -F 'EB(s) reached one' "$file" | tail -1 | sed 's/^ *//' | cut -c1-120)"
      else
        echo "$size $arm seed $seed: FAILED, see $file"
      fi
    done
  done
done
