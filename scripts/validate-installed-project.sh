#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ $# -gt 0 && "$1" != -* ]]; then
  target="$1"
  shift
  set -- --target "$target" "$@"
fi
exec python3 "$script_dir/relay.py" doctor "$@"
