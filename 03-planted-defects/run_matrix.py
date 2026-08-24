#!/usr/bin/env python3
"""
trenyx-verify-001 — detection matrix runner.

For each PLANTABLE defect: plant → run the TARGET's own suite → revert → diff the
set of failing tests against the baseline. CAUGHT = at least one test that passed
at baseline fails with the defect planted (plan §4). Writes matrix.json + matrix.md.

    python run_matrix.py <target_repo> <venv_python> [D01 D02 ...]

Baseline: the first thing this script does is run the suite unplanted and record
the failing set (01-baseline/baseline_failures.txt) so later diffs are honest even
if the target has pre-existing failures.
"""
import json
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from plant import DEFECTS, apply, revert  # noqa: E402

PYTEST = ["-q", "-p", "no:cacheprovider", "-rf", "--timeout=300", "-x0"]


def run_suite(repo: Path, py: str) -> tuple[set[str], str, float]:
    """Return (failing test ids, tail of output, seconds)."""
    t0 = time.time()
    cmd = [py, "-m", "pytest", "-q", "-p", "no:cacheprovider", "-rf", "--timeout=300"]
    proc = subprocess.run(cmd, cwd=repo, capture_output=True, text=True)
    out = proc.stdout + proc.stderr
    fails = set()
    for line in out.splitlines():
        if line.startswith("FAILED ") or line.startswith("ERROR "):
            fails.add(line.split(" ")[1].split(" - ")[0])
    return fails, "\n".join(out.splitlines()[-3:]), time.time() - t0


def main():
    repo, py = Path(sys.argv[1]), sys.argv[2]
    keys = sys.argv[3:] or [k for k, d in DEFECTS.items() if not d.get("status")]
    revert(repo)
    base_fails, base_tail, base_s = run_suite(repo, py)
    (HERE.parent / "01-baseline").mkdir(exist_ok=True)
    (HERE.parent / "01-baseline" / "baseline_failures.txt").write_text(
        "\n".join(sorted(base_fails)) + "\n"
    )
    print(f"baseline: {len(base_fails)} pre-existing failures | {base_tail.splitlines()[-1] if base_tail else ''} | {base_s:.0f}s")

    rows = []
    for k in keys:
        d = DEFECTS[k]
        if d.get("status"):
            rows.append(dict(id=k, title=d["title"], status=d["status"], reason=d["reason"]))
            continue
        apply(repo, k)
        try:
            fails, tail, secs = run_suite(repo, py)
        finally:
            revert(repo)
        new = sorted(fails - base_fails)
        rows.append(dict(id=k, title=d["title"], file=d["file"],
                         status="CAUGHT" if new else "ESCAPED",
                         new_failures=new, n_new=len(new), seconds=round(secs),
                         tail=tail.splitlines()[-1] if tail else ""))
        print(f"{k}: {'CAUGHT' if new else 'ESCAPED'} ({len(new)} new failures, {secs:.0f}s)")

    (HERE / "matrix.json").write_text(json.dumps(rows, indent=2))
    plantable = [r for r in rows if r["status"] in ("CAUGHT", "ESCAPED")]
    caught = [r for r in plantable if r["status"] == "CAUGHT"]
    md = ["# Detection matrix — the target's own suite vs. planted defects", "",
          f"Baseline: {len(base_fails)} pre-existing failures (01-baseline/baseline_failures.txt).", "",
          f"**Result: {len(caught)} / {len(plantable)} plantable defects caught by the target's tests.**", "",
          "| id | defect | file | result | new failing tests |", "|---|---|---|---|---|"]
    for r in rows:
        if r["status"] in ("CAUGHT", "ESCAPED"):
            names = ", ".join(t.split("::")[-1] for t in r["new_failures"][:4])
            more = f" (+{r['n_new']-4})" if r["n_new"] > 4 else ""
            md.append(f"| {r['id']} | {r['title']} | `{r['file']}` | **{r['status']}** | {names}{more} |")
        else:
            md.append(f"| {r['id']} | {r['title']} | — | {r['status']} | {r['reason']} |")
    (HERE / "matrix.md").write_text("\n".join(md) + "\n")
    print("wrote matrix.json, matrix.md")


if __name__ == "__main__":
    main()
