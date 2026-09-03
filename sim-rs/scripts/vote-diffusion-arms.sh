#!/usr/bin/env bash
# Run the vote diffusion arms over one scenario and print the comparison.
#
# Every arm delivers the same votes; they differ only in what they spend to do
# it. Summary output only, no trace files, so a run costs minutes and megabytes
# rather than hours and gigabytes.
#
#   ./scripts/vote-diffusion-arms.sh [-t topology] [-s slots] [-p extra.yaml]...
#
# Arms are defined by the parameters/vote-*.yaml overlays.
# push-no-dedupe is deliberately absent: it does not terminate.

set -euo pipefail
cd "$(dirname "$0")/.."

TOPOLOGY="test_data/thousand.yaml"
SLOTS=300
EXTRA=(-p parameters/linear-with-tx-references.yaml -p parameters/turbo.yaml)
COMMITTEE="everyone"
SEED=0

while getopts "t:s:p:c:S:h" opt; do
  case "$opt" in
    t) TOPOLOGY="$OPTARG" ;;
    s) SLOTS="$OPTARG" ;;
    p) EXTRA+=(-p "$OPTARG") ;;
    c) COMMITTEE="$OPTARG" ;;
    S) SEED="$OPTARG" ;;
    h) sed -n '2,12p' "$0"; exit 0 ;;
    *) exit 1 ;;
  esac
done

# Always rebuild: a stale binary silently rejects newly added strategy values
# and produces an empty comparison rather than an error you would notice.
BIN="target/release/sim-cli"
cargo build --release

SCENARIO="$(mktemp -t vote-arms-scenario)"
trap 'rm -f "$SCENARIO"' EXIT
cat > "$SCENARIO" <<YAML
committee-selection-algorithm: "$COMMITTEE"
quorum-weight-fraction: 0.75
seed: $SEED
YAML

echo "topology=$TOPOLOGY slots=$SLOTS committee=$COMMITTEE seed=$SEED"
echo "binary=$("$BIN" --version)"
echo

for arm in announce push push-late-dedupe push-echo; do
  out=$("$BIN" "$TOPOLOGY" -s "$SLOTS" "${EXTRA[@]}" \
        -p "$SCENARIO" -p "parameters/vote-$arm.yaml" 2>&1 |
        sed 's/\x1b\[[0-9;]*m//g')
  votes=$(echo "$out" | grep -o '[0-9]* total votes were generated' | tail -1 | awk '{print $1}')
  printf '%-18s votes=%-7s %s\n' "$arm" "${votes:-?}" \
    "$(echo "$out" | grep 'Vote message(s)' | tail -1 | sed 's/^ *//')"
done
