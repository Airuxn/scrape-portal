#!/usr/bin/env bash
# Vercel Ignored Build Step: wait for GitHub CI + CodeQL on main before deploying.
# Exit 0 = proceed with build; exit 1 = skip build.
# Public repo — no GitHub token required.
set -euo pipefail

ref="${VERCEL_GIT_COMMIT_REF:-}"
if [ "$ref" != "main" ] && [ "$ref" != "master" ]; then
  exit 0
fi

commit="${VERCEL_GIT_COMMIT_SHA:?}"
owner="Airuxn"
repo="scrape-portal"
api="https://api.github.com/repos/${owner}/${repo}/commits/${commit}/status"

max_attempts=90
sleep_seconds=20

github_state() {
  python3 - <<'PY' "$api"
import json
import sys
import urllib.request

url = sys.argv[1]
try:
    with urllib.request.urlopen(url, timeout=30) as resp:
        data = json.load(resp)
    print(data.get("state", "pending"))
except Exception:
    print("pending")
PY
}

for attempt in $(seq 1 "$max_attempts"); do
  state=$(github_state)
  case "$state" in
    success)
      echo "GitHub checks passed for ${commit:0:7}"
      exit 0
      ;;
    failure|error)
      echo "GitHub checks failed (${state}) for ${commit:0:7}" >&2
      exit 1
      ;;
    *)
      echo "Waiting for GitHub CI + CodeQL (${attempt}/${max_attempts}, state=${state})..."
      sleep "$sleep_seconds"
      ;;
  esac
done

echo "Timed out waiting for GitHub checks on ${commit:0:7}" >&2
exit 1
