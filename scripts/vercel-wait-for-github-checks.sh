#!/usr/bin/env bash
# Vercel Ignored Build Step: wait for GitHub CI + CodeQL before deploying.
# Applies to production (main) and PR preview builds — not just main.
# Vercel semantics: exit 0 = SKIP build, exit 1 = RUN build.
# Uses check-runs (not /status — Vercel posts pending there while this script runs).
set -euo pipefail

commit="${VERCEL_GIT_COMMIT_SHA:?}"
ref="${VERCEL_GIT_COMMIT_REF:-unknown}"
owner="${VERCEL_GIT_REPO_OWNER:-Airuxn}"
repo="${VERCEL_GIT_REPO_SLUG:?}"

max_attempts=60
sleep_seconds=30

evaluate_checks() {
  python3 - <<'PY' "$owner" "$repo" "$commit"
import json
import sys
import urllib.error
import urllib.request

owner, repo, sha = sys.argv[1:4]
ignored_apps = {"vercel"}

runs = []
page = 1
while True:
    url = (
        f"https://api.github.com/repos/{owner}/{repo}/commits/{sha}/check-runs"
        f"?per_page=100&page={page}"
    )
    try:
        with urllib.request.urlopen(url, timeout=30) as resp:
            data = json.load(resp)
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            print("pending")
            sys.exit(0)
        print("pending")
        sys.exit(0)
    except Exception:
        print("pending")
        sys.exit(0)

    batch = data.get("check_runs") or []
    runs.extend(batch)
    if len(batch) < 100:
        break
    page += 1

relevant = [r for r in runs if (r.get("app") or {}).get("slug") not in ignored_apps]

if not relevant:
    print("pending")
    sys.exit(0)

incomplete = [r["name"] for r in relevant if r.get("status") != "completed"]
if incomplete:
    print(f"pending ({len(incomplete)} running: {', '.join(incomplete[:3])})")
    sys.exit(0)

failed = [
    r["name"]
    for r in relevant
    if r.get("conclusion") not in ("success", "skipped", "neutral")
]
if failed:
    print(f"failure ({', '.join(failed[:5])})")
    sys.exit(0)

tests = [r for r in relevant if r.get("name") == "test"]
if not tests or tests[0].get("conclusion") != "success":
    print("pending (CI test job not successful yet)")
    sys.exit(0)

analyses = [r for r in relevant if str(r.get("name", "")).startswith("Analyze (")]
if not analyses:
    print("pending (CodeQL not started yet)")
    sys.exit(0)

pending_analyses = [r["name"] for r in analyses if r.get("conclusion") != "success"]
if pending_analyses:
    print(f"pending (CodeQL: {', '.join(pending_analyses[:3])})")
    sys.exit(0)

print("success")
PY
}

for attempt in $(seq 1 "$max_attempts"); do
  result=$(evaluate_checks)
  case "$result" in
    success)
      echo "GitHub CI + CodeQL passed for ${owner}/${repo}@${commit:0:7} on ${ref} — proceeding with Vercel build"
      exit 1
      ;;
    failure*)
      echo "GitHub checks failed for ${commit:0:7}: ${result} — skipping deploy" >&2
      exit 0
      ;;
    *)
      echo "Waiting for GitHub CI + CodeQL (${attempt}/${max_attempts}): ${result}"
      sleep "$sleep_seconds"
      ;;
  esac
done

echo "Timed out waiting for GitHub checks on ${commit:0:7} — skipping deploy" >&2
exit 0
