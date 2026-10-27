"""Run a persona scenario against a scratch database and write a QA report.

Examples:
    python scripts/qa_run.py --persona P2 --scenario P2-J1
    python scripts/qa_run.py --persona P2 --all

Exit codes:
    0  all checks passed
    1  product/contract findings (the report lists them)
    2  harness or scenario error

The run never opens the live pilot database. Reports and scratch data are
written under ``instance/qa`` (gitignored), or next to an explicit ``--db``.
"""
import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8", errors="replace")

from drugshop.apps.service import current_plan  # noqa: E402
from qa.harness import (  # noqa: E402
    assert_scratch_path,
    build_scratch_app,
    db_sha256,
    git_commit,
)
from qa.runner import ScenarioRunner  # noqa: E402
from qa.seeds import summary_counts  # noqa: E402
from qa.specs import load_personas, load_scenario, load_scenarios, persona_by_id  # noqa: E402


def _utm_stamp():
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def _select_scenarios(persona, args):
    available = load_scenarios(persona["id"])
    if args.scenario:
        selected = [load_scenario(persona["id"], scenario_id) for scenario_id in args.scenario]
    else:
        selected = available
    ids = {scenario["id"] for scenario in selected}
    missing = sorted(ids - {scenario["id"] for scenario in available})
    if missing:
        raise SystemExit(f"scenario(s) not defined for {persona['id']}: {', '.join(missing)}")
    return selected


def _build_summary(report):
    persona = report["persona"]
    run = report["run"]
    scenarios = report["scenarios"]
    findings = report["findings"]
    lines = [
        f"# QA run — {persona['id']} {persona['name']}",
        "",
        f"**Result:** {run['result'].upper()}",
        "",
        "| Field | Value |",
        "|---|---|",
        f"| Run | `{run['id']}` |",
        f"| Commit | `{run['git_commit']}` |",
        f"| Persona | {persona['name']} ({persona['role']}) |",
        f"| Plan | `{run['plan']}` |",
        f"| Seed | `{run['seed']}` |",
        f"| Mode | {run['mode']} |",
        f"| Scratch DB | `{run['db_path']}` |",
        f"| DB SHA256 | `{run['db_sha256']}` |",
        f"| Started | {run['started_at']} |",
        f"| Duration | {run['duration_ms']} ms |",
        "",
        "## Scenario results",
        "",
        "| Scenario | Result | Checks | Duration | UX actions |",
        "|---|---|---:|---:|---:|",
    ]
    for scenario in scenarios:
        passed = sum(1 for step in scenario["steps"] if step["ok"])
        total = len(scenario["steps"])
        ux = scenario.get("ux_actions")
        ux_label = "—" if ux is None else f"{ux}/{scenario.get('budget_actions', '—')}"
        lines.append(
            f"| {scenario['id']} — {scenario['name']} | {scenario['result'].upper()} "
            f"| {passed}/{total} | {scenario['duration_ms']} ms | {ux_label} |"
        )

    lines.extend(["", "## Findings", ""])
    if findings:
        lines.extend(
            [
                "| Severity | Scenario | Check | Expected | Actual |",
                "|---|---|---|---|---|",
            ]
        )
        for finding in findings:
            lines.append(
                f"| {finding['severity']} | {finding['scenario']} | {finding['check']} "
                f"| {finding['expected'] or '—'} | {finding['actual'] or '—'} |"
            )
    else:
        lines.append("No contract or assertion findings in this run.")

    lines.extend(
        [
            "",
            "## PMF proxies",
            "",
            "| Signal | Value | Reading |",
            "|---|---:|---|",
            f"| Scenario completion | {report['pmf']['scenario_completion']:.0%} | "
            "Share of selected journeys that completed without findings |",
            f"| Contract gaps | {report['pmf']['contract_gaps']} | "
            "Security or product claims that do not match the running app |",
            f"| Friction events | {report['pmf']['friction_events']} | "
            "Assertions or harness errors, excluding contract gaps |",
            f"| Server-side time | {report['pmf']['server_time_ms']} ms | "
            "In-process API time, not browser or network time |",
            "",
            "## What this run proves",
            "",
            "- The selected journeys ran against a fresh seeded database.",
            "- Every recorded step has an expected value, an actual value, and evidence in the JSON report.",
            "- Where a journey completed, the database reached the expected state.",
            "",
            "## What this run does not prove",
            "",
            "- Browser layout, touch targets, loading states, or console errors.",
            "- Real network latency on a counter tablet.",
            "- Willingness to pay, retention, or product-market fit.",
            "- Any assertion about the live pilot database.",
            "",
            "Use the browser/manual checklist in `qa/report-template.md` for the missing UX layer.",
            "",
            "## Evidence",
            "",
            f"- JSON report: `{run['report_json']}`",
            f"- Scratch database: `{run['db_path']}`",
            f"- Upload directory: `{run['upload_dir']}`",
            "",
        ]
    )
    return "\n".join(lines)


def _finding_actions(findings):
    if not findings:
        return ["No action required for this run."]
    actions = []
    for finding in findings:
        detail = finding["detail"]
        if detail == f"expected HTTP {finding['expected']}, got {finding['actual']}":
            detail = ""
        suffix = f" {detail}" if detail else ""
        actions.append(
            f"- **{finding['severity']}** {finding['scenario']} / {finding['check']}: "
            f"expected {finding['expected'] or 'success'}, got {finding['actual'] or 'failure'}."
            f"{suffix}"
        )
    return actions


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--persona", default="P2", help="persona id (default: P2)")
    parser.add_argument("--scenario", action="append", help="scenario id; repeat for more than one")
    parser.add_argument("--all", action="store_true", help="run every scenario for the persona")
    parser.add_argument("--plan", help="override the persona/scenario plan")
    parser.add_argument("--seed", help="override the scenario seed profile")
    parser.add_argument("--db", help="scratch database path (default: a new instance/qa/run-*)")
    parser.add_argument("--list", action="store_true", help="list personas and scenarios")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)

    personas = load_personas()
    if args.list:
        for persona in personas:
            print(f"{persona['id']} {persona['name']} — {persona['role']} / {persona['plan']} / {persona['surface']}")
            try:
                scenarios = load_scenarios(persona["id"])
            except FileNotFoundError:
                print("   (no executable scenarios yet)")
                continue
            for scenario in scenarios:
                print(f"   {scenario['id']} — {scenario['name']}")
        return 0

    persona = persona_by_id(args.persona)
    try:
        selected = _select_scenarios(persona, args)
    except FileNotFoundError as exc:
        raise SystemExit(str(exc)) from exc
    if not selected:
        raise SystemExit(f"no executable scenarios for {persona['id']} yet")

    seeds = {scenario.get("seed", "pharmacy_day") for scenario in selected}
    plans = {scenario.get("plan", persona["plan"]) for scenario in selected}
    if len(seeds) > 1:
        raise SystemExit("selected scenarios use different seeds; run them separately")
    if len(plans) > 1:
        raise SystemExit("selected scenarios use different plans; run them separately")
    seed = args.seed or seeds.pop()
    plan = args.plan or plans.pop()

    run_id = _utm_stamp()
    if args.db:
        db_path = assert_scratch_path(args.db)
        run_dir = db_path.parent
        report_dir = run_dir / f"qa-report-{run_id}"
    else:
        run_dir = PROJECT_ROOT / "instance" / "qa" / f"run-{run_id}"
        db_path = run_dir / "drugshop.db"
        report_dir = run_dir
    upload_dir = run_dir / "uploads"
    report_dir.mkdir(parents=True, exist_ok=True)

    started_at = datetime.now().isoformat(timespec="seconds")
    app = build_scratch_app(db_path, upload_dir, plan=plan, profile=seed)
    with app.app_context():
        active_plan = current_plan()
        counts = summary_counts()

    scenario_results = []
    for scenario in selected:
        result = ScenarioRunner(app, persona, scenario).run()
        scenario_results.append(result)
        if not args.quiet:
            passed = sum(1 for step in result.steps if step.ok)
            print(f"[{result.result.upper():4}] {result.id} — {result.name} ({passed}/{len(result.steps)} checks)")
            for finding in result.findings:
                print(f"       {finding['severity']} {finding['check']}: expected {finding['expected']}, got {finding['actual']}")

    findings = [finding for result in scenario_results for finding in result.findings]
    scenario_completion = (
        sum(1 for result in scenario_results if result.result == "pass") / len(scenario_results)
        if scenario_results else 0.0
    )
    contract_gaps = sum(1 for finding in findings if finding["type"] == "contract")
    friction_events = len(findings) - contract_gaps
    server_time_ms = round(sum(result.duration_ms for result in scenario_results), 1)
    result_label = "pass" if not findings else "findings"
    if any(finding["type"] == "error" for finding in findings):
        result_label = "error"

    report = {
        "schema_version": 1,
        "run": {
            "id": run_id,
            "started_at": started_at,
            "finished_at": datetime.now().isoformat(timespec="seconds"),
            "duration_ms": server_time_ms,
            "git_commit": git_commit(),
            "persona": persona["id"],
            "plan": plan,
            "plan_label": active_plan["label"],
            "seed": seed,
            "mode": "api-in-process (Flask test client)",
            "db_path": str(db_path),
            "upload_dir": str(upload_dir),
            "db_sha256": db_sha256(db_path),
            "row_counts": counts,
            "report_json": str(report_dir / "report.json"),
            "result": result_label,
        },
        "persona": persona,
        "scenarios": [result.as_dict() for result in scenario_results],
        "findings": findings,
        "pmf": {
            "scenario_completion": round(scenario_completion, 3),
            "contract_gaps": contract_gaps,
            "friction_events": friction_events,
            "server_time_ms": server_time_ms,
        },
    }

    report_json = report_dir / "report.json"
    summary_md = report_dir / "summary.md"
    report_json.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    summary = _build_summary(report)
    summary += "\n## Recommended actions\n\n" + "\n".join(_finding_actions(findings)) + "\n"
    summary_md.write_text(summary, encoding="utf-8")

    if not args.quiet:
        print("")
        print(f"Result: {result_label.upper()} — {len(findings)} finding(s)")
        print(f"Report: {summary_md}")
        print(f"JSON:   {report_json}")
        print(f"DB:     {db_path}")

    if result_label == "error":
        return 2
    return 0 if result_label == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
