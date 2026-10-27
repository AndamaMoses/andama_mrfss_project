"""Execute one persona scenario against a scratch Flask app.

The runner records every step, its HTTP status, its timing, and the evidence
needed for a review. It deliberately keeps going after independent contract
failures when a scenario says ``continue_on_failure``; otherwise it stops at
the first failed step so a broken golden path does not produce noisy cascades.
"""
import json
import time
from dataclasses import asdict, dataclass, field

from drugshop.db import get_db
from qa.harness import password_for


class QaCheckError(AssertionError):
    """A failed expectation that belongs in the QA report, not a traceback."""

    def __init__(self, message, expected="", actual="", contract=False):
        super().__init__(message)
        self.expected = expected
        self.actual = actual
        self.contract = contract


@dataclass
class StepOutcome:
    detail: str = ""
    expected: str = ""
    actual: str = ""
    status: int | None = None
    excerpt: str = ""


@dataclass
class StepResult:
    index: int
    action: str
    label: str
    ok: bool
    ms: float
    detail: str = ""
    expected: str = ""
    actual: str = ""
    status: int | None = None
    excerpt: str = ""
    error_type: str = ""

    def as_dict(self):
        return asdict(self)


@dataclass
class ScenarioResult:
    id: str
    name: str
    result: str
    steps: list[StepResult] = field(default_factory=list)
    duration_ms: float = 0.0
    budget_seconds: float | None = None
    ux_actions: int | None = None
    budget_actions: int | None = None
    stopped_early: bool = False
    findings: list[dict] = field(default_factory=list)

    def as_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "result": self.result,
            "duration_ms": round(self.duration_ms, 1),
            "budget_seconds": self.budget_seconds,
            "ux_actions": self.ux_actions,
            "budget_actions": self.budget_actions,
            "stopped_early": self.stopped_early,
            "steps": [step.as_dict() for step in self.steps],
            "findings": self.findings,
        }


def _get_path(data, path):
    if path in ("", None):
        return data
    current = data
    for part in str(path).split("."):
        if isinstance(current, list):
            try:
                current = current[int(part)]
            except (ValueError, IndexError) as exc:
                raise QaCheckError(
                    f"list index {part!r} not found in {path!r}",
                    expected=path,
                    actual=repr(current)[:200],
                ) from exc
        elif isinstance(current, dict):
            if part not in current:
                raise QaCheckError(
                    f"key {part!r} not found in {path!r}",
                    expected=path,
                    actual=", ".join(current.keys())[:200],
                )
            current = current[part]
        else:
            raise QaCheckError(
                f"cannot descend into {type(current).__name__} at {part!r}",
                expected=path,
                actual=repr(current)[:200],
            )
    return current


def _spec_label(spec):
    keys = ("equals", "contains", "length", "length_gte", "gte", "lte", "in")
    return ", ".join(f"{key}={spec[key]!r}" for key in keys if key in spec)


class ScenarioRunner:
    def __init__(self, app, persona, scenario):
        self.app = app
        self.persona = persona
        self.scenario = scenario
        self.client = app.test_client()
        self.ctx = {"persona": persona, "scenario": scenario}
        self.last_json = None
        self._last_status = None
        self._last_excerpt = ""

    def run(self):
        started = time.perf_counter()
        steps = self.scenario.get("steps", [])
        if not steps:
            raise ValueError(f"scenario {self.scenario.get('id')} has no steps")

        continue_on_failure = bool(self.scenario.get("continue_on_failure"))
        results = []
        stopped_early = False

        for index, step in enumerate(steps, 1):
            self._last_status = None
            self._last_excerpt = ""
            step_started = time.perf_counter()
            error_type = ""
            try:
                outcome = self._dispatch(step)
                ok = True
            except QaCheckError as exc:
                ok = False
                error_type = "contract" if exc.contract else "assert"
                outcome = StepOutcome(
                    detail=str(exc),
                    expected=exc.expected,
                    actual=exc.actual,
                    status=self._last_status,
                    excerpt=self._last_excerpt,
                )
            except Exception as exc:  # noqa: BLE001 - report it, do not abort the run
                ok = False
                error_type = "error"
                outcome = StepOutcome(
                    detail=f"{type(exc).__name__}: {exc}",
                    status=self._last_status,
                    excerpt=self._last_excerpt,
                )

            elapsed = (time.perf_counter() - step_started) * 1000
            results.append(
                StepResult(
                    index=index,
                    action=step.get("action", "unknown"),
                    label=step.get("label") or step.get("action", "step"),
                    ok=ok,
                    ms=round(elapsed, 1),
                    detail=outcome.detail,
                    expected=outcome.expected,
                    actual=outcome.actual,
                    status=outcome.status,
                    excerpt=outcome.excerpt,
                    error_type=error_type,
                )
            )

            if not ok and (not continue_on_failure or step.get("action") == "login"):
                stopped_early = index < len(steps)
                break

        duration_ms = (time.perf_counter() - started) * 1000
        findings = self._findings(results)
        result = "pass" if not findings else "fail"
        return ScenarioResult(
            id=self.scenario["id"],
            name=self.scenario.get("name", self.scenario["id"]),
            result=result,
            steps=results,
            duration_ms=duration_ms,
            budget_seconds=self.scenario.get("budget_seconds"),
            ux_actions=self.scenario.get("ux_actions"),
            budget_actions=self.scenario.get("budget_actions"),
            stopped_early=stopped_early,
            findings=findings,
        )

    def _dispatch(self, step):
        action = step.get("action")
        handler = getattr(self, f"_step_{action}", None)
        if handler is None:
            raise QaCheckError(f"unknown scenario action {action!r}")
        return handler(step)

    # ---------- steps ----------
    def _step_login(self, step):
        username = self.persona["username"]
        response = self.client.post(
            "/api/login",
            json={"username": username, "password": password_for(self.persona)},
        )
        self._expect_status(response, step.get("expect_status", 200))
        data = response.get_json() or {}
        if data.get("username") != username:
            raise QaCheckError(
                f"login returned {data.get('username')!r}, not {username!r}",
                expected=username,
                actual=repr(data.get("username")),
            )
        self.last_json = data
        self.ctx["me"] = data
        return StepOutcome(
            detail=f"signed in as {data.get('display_name') or username} ({data.get('role')})",
            expected="200",
            actual=str(response.status_code),
            status=response.status_code,
            excerpt=self._excerpt(response),
        )

    def _step_lookup_product(self, step):
        name = step["name"]
        product = self._product(name)
        key = step.get("save") or _slug(name)
        self.ctx.setdefault("products", {})[name] = product
        self.ctx[key] = product
        return StepOutcome(
            detail=f"{name}: id={product['id']} stock={product.get('stock_on_hand')} "
                   f"sell={product.get('price_sell')}",
            expected="product present with stock > 0",
            actual=f"id={product['id']} stock={product.get('stock_on_hand')}",
        )

    def _step_sell(self, step):
        items = []
        for item in step.get("items", []):
            name = item["product_name"]
            product = self.ctx.get("products", {}).get(name) or self._product(name)
            self.ctx.setdefault("products", {})[name] = product
            items.append({"product_id": product["id"], "qty": int(item["qty"])})

        payload = {
            "items": items,
            "payment_method": step.get("payment_method", "CASH"),
            "served_by": step.get("served_by", self.persona["username"]),
        }
        for optional in ("customer_name", "customer_phone", "sale_date"):
            if step.get(optional):
                payload[optional] = step[optional]

        response = self.client.post("/api/sales/cart", json=payload)
        self._expect_status(response, step.get("expect_status", 201))
        data = response.get_json() or {}
        self.last_json = data
        self._save(data, step.get("save"))
        return StepOutcome(
            detail=f"receipt={data.get('receipt_ref')} total={data.get('total')} "
                   f"lines={data.get('lines')}",
            expected=str(step.get("expect_status", 201)),
            actual=str(response.status_code),
            status=response.status_code,
            excerpt=self._excerpt(response),
        )

    def _step_http(self, step):
        method = step.get("method", "GET").upper()
        path = self._format(step["path"])
        payload = self._resolve(step.get("json"))
        if payload is None:
            response = self.client.open(path, method=method)
        else:
            response = self.client.open(path, method=method, json=payload)

        self._last_status = response.status_code
        self._last_excerpt = self._excerpt(response)
        self._expect_status(response, step.get("expect_status", 200))

        if response.is_json:
            self.last_json = response.get_json()
            self._save(self.last_json, step.get("save"))
        detail = f"{method} {path} -> {response.status_code}"
        return StepOutcome(
            detail=detail,
            expected=str(step.get("expect_status", 200)),
            actual=str(response.status_code),
            status=response.status_code,
            excerpt=self._last_excerpt,
        )

    def _step_assert_json(self, step):
        if self.last_json is None:
            raise QaCheckError("no JSON response available to assert")
        value = _get_path(self.last_json, step["path"])
        expected, actual = self._check(value, step)
        return StepOutcome(detail=f"{step['path']} = {value!r}", expected=expected, actual=actual)

    def _step_assert_context(self, step):
        key = step["key"]
        if key not in self.ctx:
            raise QaCheckError(f"context key {key!r} is not set", expected=key)
        value = self.ctx[key]
        expected, actual = self._check(value, step)
        return StepOutcome(detail=f"{key} = {value!r}", expected=expected, actual=actual)

    def _step_db(self, step):
        args = [self._resolve(arg) for arg in step.get("args", [])]
        db = get_db()
        try:
            row = db.execute(step["sql"], args).fetchone()
            value = row[0] if row else None
        finally:
            db.close()
        if step.get("save"):
            self.ctx[step["save"]] = value
        if any(key in step for key in ("equals", "contains", "length", "length_gte", "gte", "lte", "in")):
            expected, actual = self._check(value, step)
        else:
            expected, actual = "value captured", repr(value)
        return StepOutcome(detail=f"db -> {value!r}", expected=expected, actual=actual)

    def _step_assert_delta(self, step):
        left = self.ctx.get(step["left"])
        right = self.ctx.get(step["right"])
        if left is None or right is None:
            raise QaCheckError(
                f"delta needs both {step['left']!r} and {step['right']!r}",
                expected="both context values set",
                actual=f"{left!r}, {right!r}",
            )
        actual = right - left
        expected, actual_label = self._check(actual, {"equals": step["equals"]})
        return StepOutcome(
            detail=f"{step['right']} - {step['left']} = {actual}",
            expected=expected,
            actual=actual_label,
        )

    def _step_note(self, step):
        return StepOutcome(detail=step.get("text", ""))

    # ---------- helpers ----------
    def _product(self, name):
        response = self.client.get("/api/products")
        self._expect_status(response, 200)
        rows = response.get_json() or []
        product = next((row for row in rows if row.get("name") == name), None)
        if product is None:
            raise QaCheckError(
                f"product {name!r} not found in /api/products",
                expected=name,
                actual=", ".join(row.get("name", "") for row in rows)[:300],
            )
        if (product.get("stock_on_hand") or 0) <= 0:
            raise QaCheckError(
                f"product {name!r} has no stock",
                expected="stock > 0",
                actual=str(product.get("stock_on_hand")),
            )
        return product

    def _expect_status(self, response, expected):
        if response.status_code != expected:
            raise QaCheckError(
                f"expected HTTP {expected}, got {response.status_code}",
                expected=str(expected),
                actual=str(response.status_code),
                contract=True,
            )

    def _check(self, value, spec):
        expected = _spec_label(spec)
        actual = repr(value)
        if "equals" in spec:
            want = self._resolve(spec["equals"])
            if value != want:
                raise QaCheckError(
                    f"expected {want!r}, got {value!r}",
                    expected=expected,
                    actual=actual,
                )
        elif "contains" in spec:
            want = self._resolve(spec["contains"])
            if want not in value:
                raise QaCheckError(
                    f"expected {value!r} to contain {want!r}",
                    expected=expected,
                    actual=actual,
                )
        elif "length" in spec:
            want = int(spec["length"])
            if len(value) != want:
                raise QaCheckError(
                    f"expected length {want}, got {len(value)}",
                    expected=expected,
                    actual=actual,
                )
        elif "length_gte" in spec:
            want = int(spec["length_gte"])
            if len(value) < want:
                raise QaCheckError(
                    f"expected length >= {want}, got {len(value)}",
                    expected=expected,
                    actual=actual,
                )
        elif "gte" in spec:
            want = spec["gte"]
            if value < want:
                raise QaCheckError(
                    f"expected >= {want!r}, got {value!r}",
                    expected=expected,
                    actual=actual,
                )
        elif "lte" in spec:
            want = spec["lte"]
            if value > want:
                raise QaCheckError(
                    f"expected <= {want!r}, got {value!r}",
                    expected=expected,
                    actual=actual,
                )
        elif "in" in spec:
            want = self._resolve(spec["in"])
            if value not in want:
                raise QaCheckError(
                    f"expected {value!r} in {want!r}",
                    expected=expected,
                    actual=actual,
                )
        else:
            raise QaCheckError(
                "assertion step has no equals/contains/length/gte/lte/in key",
                expected=expected,
                actual=actual,
            )
        return expected, actual

    def _save(self, data, mapping):
        if not mapping:
            return
        if isinstance(mapping, str):
            self.ctx[mapping] = data
            return
        for key, path in mapping.items():
            if path == "$json":
                self.ctx[key] = data
            else:
                self.ctx[key] = _get_path(data, path)

    def _format(self, value):
        if not isinstance(value, str) or "{" not in value:
            return value
        try:
            return value.format(**self.ctx)
        except KeyError as exc:
            raise QaCheckError(
                f"unresolved placeholder {exc}",
                expected="a context value",
                actual=value,
            ) from exc

    def _resolve(self, value):
        if isinstance(value, str):
            return self._format(value)
        if isinstance(value, list):
            return [self._resolve(item) for item in value]
        if isinstance(value, dict):
            return {key: self._resolve(item) for key, item in value.items()}
        return value

    def _excerpt(self, response):
        if response.is_json:
            return json.dumps(response.get_json(), ensure_ascii=False)[:500]
        if (response.mimetype or "").startswith("text/"):
            return response.get_data(as_text=True)[:500]
        return f"<{response.mimetype or 'unknown'} {len(response.data)} bytes>"

    def _findings(self, results):
        findings = []
        for step in results:
            if step.ok:
                continue
            severity = "P1" if step.error_type in ("contract", "assert") else "P2"
            findings.append(
                {
                    "severity": severity,
                    "type": step.error_type,
                    "scenario": self.scenario["id"],
                    "step": step.index,
                    "check": step.label,
                    "expected": step.expected,
                    "actual": step.actual,
                    "detail": step.detail,
                    "evidence": f"report.json#scenarios/{self.scenario['id']}/steps/{step.index}",
                }
            )
        if (
            self.scenario.get("ux_actions") is not None
            and self.scenario.get("budget_actions") is not None
            and self.scenario["ux_actions"] > self.scenario["budget_actions"]
        ):
            findings.append(
                {
                    "severity": "P2",
                    "type": "budget",
                    "scenario": self.scenario["id"],
                    "check": "user action budget",
                    "expected": f"<= {self.scenario['budget_actions']} actions",
                    "actual": f"{self.scenario['ux_actions']} actions",
                    "detail": "The scenario exceeds its UX action budget.",
                    "evidence": "scenario metadata",
                }
            )
        return findings


def _slug(value):
    return "".join(ch.lower() if ch.isalnum() else "_" for ch in value).strip("_")
