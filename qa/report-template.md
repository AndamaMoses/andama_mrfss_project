# Persona QA report — P?

> Use this template for the browser/manual layer. The automated runner writes
> `instance/qa/run-*/summary.md`; this template adds what the API cannot see:
> layout, touch, loading states, console errors, and the reviewer's judgment.

## Run metadata

| Field | Value |
|---|---|
| Persona | P? — Name |
| Reviewer | |
| Date | |
| Commit | |
| Plan | |
| Seed profile | |
| Viewport | 1440×900 / 1024×768 / 390×844 |
| Browser | |
| Network | Normal / throttled 3G |
| Scenario version | |

## Verdict

- Overall: PASS / PASS WITH FINDINGS / FAIL
- PMF readiness: READY / CLOSE / NOT READY
- One sentence on whether this persona can complete their core job.

## Journey results

| Scenario | Result | User actions | Time | Evidence |
|---|---|---:|---:|---|
| P?-J1 | | | | |
| P?-N1 | | | | |

## Contract findings

| Severity | Scenario | Check | Expected | Actual | Evidence |
|---|---|---|---|---|---|
| | | | | | |

Severity:
- **P0** — data loss, security exposure, or an unusable install.
- **P1** — blocks the persona's core job or a paid-plan boundary.
- **P2** — friction, ambiguity, or a slow path.
- **P3** — polish, copy, or visual issue.

## Friction log

Record what the persona would actually experience, not implementation details.

| # | Where | What happened | Persona impact | Severity | Screenshot / console |
|---|---|---|---|---|---|
| 1 | | | | | |

## PMF readiness

| Dimension | Evidence | Score (0–2) | Notes |
|---|---|---:|---|
| Time to first value | | | |
| Core task completion | | | |
| Friction / dead ends | | | |
| Mistake recovery | | | |
| Data trust | | | |
| Plan clarity | | | |
| Mobile viability | | | |
| Support dependence | | | |

Scores: `2` = no help needed; `1` = completed with friction; `0` = blocked.
Do not claim product-market fit from this table. It is a readiness proxy.

## Evidence

- Automated JSON: `report.json`
- Automated summary: `summary.md`
- Screenshots: `screenshots/`
- Console log: `console.log`
- Network log: `network.json`
- Scratch DB SHA256: 

## Recommended actions

1. **P1** — 
2. **P2** — 
3. **P3** — 

## Coverage updates

- New scenario needed:
- Scenario that should be retired:
- Doc/code mismatch found:
- Persona assumption invalidated:
