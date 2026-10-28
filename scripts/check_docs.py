#!/usr/bin/env python
"""Check the README and docs/ against the repository. No model calls, no network.

  1. Every metric row in a results table matches the stored evaluation summary
     (docs/results/evaluation_latest.json): mean, min-max, threshold, status.
     If the original result file exists in ARTIFACTS_DIR, the summary must match it too.
  2. Stated facts (cases, repetitions, model, commit, dataset sizes, model calls) match
     the stored results and data/golden_dataset_v2.json.
  3. Relative links and anchors resolve; referenced scripts, npm scripts and paths exist.
  4. No secrets and no local machine paths.
  5. No unsupported claims (production-ready, multi-agent, cloud deployment, certification,
     compliance, expert validation, drug pharmacovigilance scope) unless the line negates them.
  6. With --count-tests: test counts in README and docs/development.md match the suites.

Usage: python scripts/check_docs.py [--count-tests]
Exit code 1 if any check fails.
"""

import argparse
import json
import re
import shutil
import subprocess
import sys
import unicodedata
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

FIXTURE = ROOT / "docs" / "results" / "evaluation_latest.json"
DATASET = ROOT / "data" / "golden_dataset_v2.json"
DOCS = [ROOT / "README.md", ROOT / "README.es.md", *sorted((ROOT / "docs").glob("*.md"))]
DOCS += [ROOT / "frontend" / "DESIGN.md"]

errors: list[str] = []
notes: list[str] = []


def fail(where: str, message: str) -> None:
    errors.append(f"{where}: {message}")


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


# --- 1. metric tables ---------------------------------------------------------------

_ROW = re.compile(r"^\|\s*`(?P<name>[a-z0-9_]+)`\s*\|(?P<rest>.+)\|\s*$")
_OPS = {"≥": ">=", "≤": "<=", "<": "<", ">": ">"}


def _value(text: str, latency: bool) -> float | None:
    text = text.strip().replace(",", ".")
    if text in ("n/a", "—", "-"):
        return None
    m = re.fullmatch(r"(-?\d+(?:\.\d+)?)\s*(%|s)", text)
    if not m:
        raise ValueError(f"unreadable value {text!r}")
    number = float(m.group(1))
    if latency != (m.group(2) == "s"):
        raise ValueError(f"unit mismatch in {text!r}")
    return number


def _expected(value: float | None, latency: bool) -> float | None:
    """Display value with one decimal, rounded half-up on the decimal digits (as the UI does)."""
    if value is None:
        return None
    scaled = Decimal(str(value)) / 1000 if latency else Decimal(str(value)) * 100
    return float(scaled.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))


def check_metric_tables(summary: dict) -> int:
    rows = 0
    for doc in DOCS:
        for n, line in enumerate(doc.read_text(encoding="utf-8").splitlines(), 1):
            m = _ROW.match(line)
            if not m or m.group("name") not in summary:
                continue
            cells = [c.strip() for c in m.group("rest").split("|")]
            if len(cells) != 4:
                continue  # definition tables have a single text column
            where = f"{rel(doc)}:{n} {m.group('name')}"
            stat = summary[m.group("name")]
            latency = m.group("name").endswith("_ms")
            rows += 1
            try:
                mean = _value(cells[0], latency)
                low, high = (
                    (None, None)
                    if cells[1] == "n/a"
                    else [_value(x, latency) for x in re.split(r"\s+–\s+", cells[1])]
                )
            except ValueError as exc:
                fail(where, str(exc))
                continue
            for label, shown, stored in (
                ("mean", mean, stat["mean"]),
                ("min", low, stat["min"]),
                ("max", high, stat["max"]),
            ):
                if shown != _expected(stored, latency):
                    fail(where, f"{label} {shown} != stored {_expected(stored, latency)}")

            threshold = stat.get("threshold") or None
            shown_threshold = cells[2]
            if threshold is None:
                if shown_threshold != "—":
                    fail(where, f"threshold shown as {shown_threshold!r} but none is configured")
            else:
                tm = re.fullmatch(r"([≥≤<>])\s*(.+)", shown_threshold)
                if not tm:
                    fail(where, f"unreadable threshold {shown_threshold!r}")
                else:
                    op = _OPS[tm.group(1)]
                    try:
                        value = _value(tm.group(2), latency)
                    except ValueError as exc:
                        fail(where, str(exc))
                        value = None
                    if op != threshold["op"] or value != _expected(threshold["value"], latency):
                        fail(where, f"threshold {shown_threshold!r} != stored {threshold}")

            gate = bool(threshold) and threshold.get("gate", True)
            status = cells[3]
            if gate and stat["meets_threshold"] is True and status != "✅":
                fail(where, f"status {status!r} but the stored result meets the threshold")
            if gate and stat["meets_threshold"] is False and status != "❌":
                fail(where, f"status {status!r} but the stored result misses the threshold")
            if not gate and status in ("✅", "❌"):
                fail(where, "status shown as pass/fail for a non-gating metric")
    return rows


def check_fixture_against_artifacts(fixture: dict) -> None:
    try:
        from src.api.routes.evaluations import _load
    except Exception as exc:  # noqa: BLE001 - optional check
        notes.append(f"could not import the evaluation loader ({exc}); artifact check skipped")
        return
    latest = _load(fixture["metadata"].get("dataset", "").split("_")[-1].removesuffix(".json"))
    if latest is None or latest.source != "artifacts" or latest.file != fixture["file"]:
        notes.append(
            f"{fixture['file']} not found in ARTIFACTS_DIR; checked the versioned summary only"
        )
        return
    current = json.loads(json.dumps(latest.model_dump(exclude={"source"}), default=str))
    if current != fixture:
        fail(rel(FIXTURE), "differs from the stored result; run scripts/export_eval_fixture.py")


# --- 2. stated facts ----------------------------------------------------------------


def check_facts(fixture: dict) -> None:
    meta, summary = fixture["metadata"], fixture["summary"]
    total = summary["total_cases"]
    usage = meta.get("usage", {})
    calls = {k: v["calls"] for k, v in usage.items()}

    data = json.loads(DATASET.read_text(encoding="utf-8"))
    cases = data["cases"]
    by = lambda **kw: sum(1 for c in cases if all(c.get(k) == v for k, v in kw.items()))  # noqa: E731
    excluded = [c for c in cases if c.get("needs_expert_review")]

    required = {
        "README.md": [
            f"{total} cases × {meta['repetitions']} repetitions",
            meta["model"],
            meta["git_commit"],
            meta["timestamp"][:10],
            f"{summary['passed']} of {total} cases passed",
            f"{len(summary['flaky_cases'])} were flaky",
            f"{len(cases)} draft cases",
            f"{len(excluded)} cases flagged for review",
            f"made {sum(calls.values())} calls",
        ],
        "docs/evaluation.md": [
            f"| Cases | {len(cases)} ({by(category='rag')} RAG questions, "
            f"{by(category='classification')} incident classifications) |",
            f"{by(language='en')} English, {by(language='es')} Spanish",
            f"`dev` {by(split='dev')} cases ({by(split='dev', category='rag')} RAG, "
            f"{by(split='dev', category='classification')} classification)",
            f"`test` {by(split='test')} cases ({by(split='test', category='rag')} RAG, "
            f"{by(split='test', category='classification')} classification)",
            f"{len(excluded)} borderline cases",
            f"{total} cases scored ({meta['cases']['rag']} RAG + {meta['cases']['classification']}"
            " classification",
            f"| Repetitions | {meta['repetitions']} ",
            f"`{meta['model']}`",
            f"commit `{meta['git_commit']}`",
            meta["timestamp"][:10],
            *(f"{role} {n} calls" for role, n in calls.items()),
            f"{summary['passed']} of {total} cases passed in all three repetitions "
            f"({round(summary['passed'] / total * 100, 1)} %)",
            f"{len(summary['flaky_cases'])} were flaky; {summary['failed']} failed",
            f"made {sum(calls.values())}",
            fixture["file"],
        ],
        "docs/open_questions.md": [f"`{c['id']}` | {c['split']} |" for c in excluded]
        + [f"All {len(cases)} cases"],
        "README.es.md": [f"{total} casos × {meta['repetitions']} repeticiones", meta["git_commit"]],
    }
    for name, needles in required.items():
        text = (ROOT / name).read_text(encoding="utf-8")
        flat = re.sub(r"\s+", " ", text)
        for needle in needles:
            if needle not in text and re.sub(r"\s+", " ", needle) not in flat:
                fail(name, f"expected the stored fact {needle!r}")

    if len(fixture["failed_cases"]) != summary["failed"]:
        fail(rel(FIXTURE), "failed_cases and summary.failed disagree; re-run the re-scoring")


# --- 3. links, commands, paths ------------------------------------------------------

_LINK = re.compile(r"!?\[[^\]]*\]\(([^)\s]+)\)")
# Created at run time (ingestion, first start, builds), so absent from a fresh clone.
_GENERATED = (
    "docs/screenshots/",
    "data/pharmawatch.db",
    "data/chroma_db",
    "frontend/dist",
    "artifacts/",
)
_INLINE_PATH = re.compile(
    r"`((?:src|scripts|tests|data|config|docs|frontend|static)/[A-Za-z0-9_./-]+)`"
)


def _slug(heading: str) -> str:
    text = heading.strip().lower()
    text = "".join(ch for ch in text if unicodedata.category(ch)[0] in "LN" or ch in " -_")
    return text.replace(" ", "-")


def _anchors(doc: Path) -> set[str]:
    return {
        _slug(m.group(1))
        for m in re.finditer(r"^#{1,6}\s+(.+)$", doc.read_text(encoding="utf-8"), re.M)
    }


def check_links_and_commands() -> None:
    package = json.loads((ROOT / "frontend" / "package.json").read_text(encoding="utf-8"))
    npm_scripts = set(package["scripts"])
    for doc in DOCS:
        text = doc.read_text(encoding="utf-8")
        for m in _LINK.finditer(text):
            target = m.group(1)
            if target.startswith(("http://", "https://", "mailto:")):
                continue
            path_part, _, anchor = target.partition("#")
            dest = (doc.parent / path_part).resolve() if path_part else doc
            if not dest.exists():
                fail(rel(doc), f"broken link {target}")
            elif anchor and dest.suffix == ".md" and anchor not in _anchors(dest):
                fail(rel(doc), f"missing anchor {target}")
        for m in re.finditer(r"python (scripts/[A-Za-z0-9_]+\.py)", text):
            if not (ROOT / m.group(1)).exists():
                fail(rel(doc), f"command references missing {m.group(1)}")
        for m in re.finditer(r"npm run ([a-z0-9:]+)", text):
            if m.group(1) not in npm_scripts:
                fail(rel(doc), f"npm script '{m.group(1)}' does not exist")
        for m in _INLINE_PATH.finditer(text):
            line = text[text.rfind("\n", 0, m.start()) + 1 : text.find("\n", m.end())]
            if "removed" in line:
                continue  # the changelog names files that no longer exist
            path = m.group(1).rstrip("/.")
            if any(ch in path for ch in "*<>…") or path.startswith(_GENERATED):
                continue
            base = ROOT if not (doc.parent.name == "frontend") else doc.parent
            if not (base / path).exists() and not (ROOT / "frontend" / path).exists():
                fail(rel(doc), f"path `{path}` does not exist")


# --- 4. secrets and local paths -----------------------------------------------------

_SECRETS = [
    re.compile(r"sk-ant-[A-Za-z0-9_-]{10,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
]
_LOCAL = re.compile(r"[A-Za-z]:\\Users\\|/Users/[a-z]|/home/[a-z]|AppData", re.I)


def check_secrets_and_paths() -> None:
    for doc in DOCS:
        for n, line in enumerate(doc.read_text(encoding="utf-8").splitlines(), 1):
            if any(p.search(line) for p in _SECRETS):
                fail(f"{rel(doc)}:{n}", "looks like a secret")
            if _LOCAL.search(line):
                fail(f"{rel(doc)}:{n}", "local machine path")


# --- 5. unsupported claims ----------------------------------------------------------

_CLAIMS = [
    r"production[- ]ready",
    r"listo para producci[oó]n",
    r"multi[- ]?agent",
    r"multi[- ]?agente",
    r"\baws\b",
    r"\b(deployed|running|hosted) (on|in|to) (the )?cloud\b",
    r"\bcloud deployment\b",
    r"\bcertified\b",
    r"\bcertificad[oa]\b",
    r"\bcompliant\b",
    r"\bcumple (con )?(el|la) (mdr|normativa)",
    r"validated by (an? )?experts?",
    r"expert[- ]validated",
    r"clinically validated",
    r"validado por expertos",
    r"\bpharmacovigilance\b",
    r"\bfarmacovigilancia\b",
    r"reviewer (improves|improved|reduces|reduced|increases|increased)",
]
_NEGATION = re.compile(
    r"\b(not|no|never|without|nor|isn't|doesn't|does not|has not|have not|ni|sin|nunca)\b", re.I
)


def check_claims() -> None:
    """A claim is allowed only when its line or the line before negates it (wrapped prose)."""
    for doc in DOCS:
        lines = doc.read_text(encoding="utf-8").splitlines()
        for n, line in enumerate(lines, 1):
            window = (lines[n - 2] + " " if n > 1 else "") + line
            for pattern in _CLAIMS:
                if re.search(pattern, line, re.I) and not _NEGATION.search(window):
                    fail(f"{rel(doc)}:{n}", f"unsupported claim /{pattern}/: {line.strip()[:100]}")


# --- 6. test counts (optional) ------------------------------------------------------


def _run(cmd: list[str], cwd: Path) -> str:
    return subprocess.run(
        cmd, cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace"
    ).stdout


def check_test_counts() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    dev = (ROOT / "docs" / "development.md").read_text(encoding="utf-8")
    found: dict[str, int] = {}

    out = _run([sys.executable, "-m", "pytest", "--collect-only", "-q"], ROOT)
    if m := re.search(r"(\d+) tests? collected", out):
        found["backend"] = int(m.group(1))
    npx = shutil.which("npx")
    if npx:
        frontend = ROOT / "frontend"
        report = frontend / "test-results" / "vitest-count.json"
        report.parent.mkdir(exist_ok=True)
        _run([npx, "vitest", "run", "--reporter=json", f"--outputFile={report}"], frontend)
        if report.exists():
            found["vitest"] = json.loads(report.read_text(encoding="utf-8"))["numTotalTests"]
            report.unlink()
        if m := re.search(
            r"Total: (\d+) tests?", _run([npx, "playwright", "test", "--list"], frontend)
        ):
            found["e2e"] = int(m.group(1))
        live = _run(
            [npx, "playwright", "test", "-c", "playwright.live.config.ts", "--list"], frontend
        )
        if m := re.search(r"Total: (\d+) tests?", live):
            found["live"] = int(m.group(1))
    else:
        notes.append("npx not found: frontend test counts not checked")

    rows = {
        "backend": (
            r"\| Backend — pytest \| (\d+) \|",
            r"\| Backend \(pytest\) \| (\d+) collected",
        ),
        "vitest": (r"\| Frontend — Vitest \| (\d+) \|", r"\| Frontend unit \(Vitest\) \| (\d+) \|"),
        "e2e": (
            r"\| End-to-end — Playwright \| (\d+) \|",
            r"\| End-to-end \(Playwright\) \| (\d+) ",
        ),
        "live": (r"\| Live smoke — Playwright \| (\d+) \|", r"\| Live smoke \| (\d+) \|"),
    }
    for suite, count in found.items():
        for name, text, pattern in (
            ("README.md", readme, rows[suite][0]),
            ("docs/development.md", dev, rows[suite][1]),
        ):
            m = re.search(pattern, text)
            if not m:
                fail(name, f"no {suite} test count found")
            elif int(m.group(1)) != count:
                fail(name, f"{suite} tests: documented {m.group(1)}, actual {count}")
    notes.append("test counts: " + ", ".join(f"{k}={v}" for k, v in found.items()))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--count-tests", action="store_true", help="also count the test suites")
    args = parser.parse_args()

    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    rows = check_metric_tables(fixture["metric_summary"])
    if rows == 0:
        fail("docs", "no metric table rows found")
    check_fixture_against_artifacts(fixture)
    check_facts(fixture)
    check_links_and_commands()
    check_secrets_and_paths()
    check_claims()
    if args.count_tests:
        check_test_counts()

    placeholders = [rel(d) for d in DOCS if "<REPO_URL>" in d.read_text(encoding="utf-8")]
    if placeholders:
        notes.append("placeholder <REPO_URL> still in: " + ", ".join(placeholders))
    print(f"checked {len(DOCS)} documents, {rows} metric rows")
    for note in notes:
        print(f"note: {note}")
    for error in errors:
        print(f"FAIL {error}")
    if errors:
        sys.exit(1)
    print("OK")


if __name__ == "__main__":
    main()
