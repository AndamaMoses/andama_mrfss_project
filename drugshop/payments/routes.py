"""Admin-only MoMo endpoints used by the counter and by operations checks.

These routes never move money by themselves beyond asking MTN to push a
collection prompt to the customer's phone; the customer still approves on
their handset. The final state is read from :func:`momo_status` and recorded
against the sale by the operator.
"""

from flask import Blueprint, current_app, jsonify, request

from drugshop.auth.guards import admin_required
from drugshop.payments.momo import MomoClient, MomoError, MomoSettings

bp = Blueprint("payments", __name__)


def _settings():
    return MomoSettings.from_mapping(current_app.config)


def _client():
    return MomoClient(_settings())


@bp.route("/api/momo/health")
@admin_required
def momo_health():
    """Credential summary; ``?check=1`` also proves the token exchange works."""
    settings = _settings()
    payload = settings.status_payload
    if request.args.get("check") in {"1", "true", "yes", "on"}:
        try:
            _client().access_token()
            payload["reachable"] = True
        except MomoError as exc:
            payload["reachable"] = False
            payload["error"] = str(exc)
            return jsonify(payload), 503
    return jsonify(payload)


@bp.route("/api/momo/collect", methods=["POST"])
@admin_required
def momo_collect():
    data = request.get_json(silent=True) or {}
    try:
        result = _client().request_to_pay(
            amount=data.get("amount"),
            phone=data.get("phone") or data.get("payer"),
            external_id=data.get("external_id") or data.get("sale_id") or "",
            reference_id=data.get("reference_id") or None,
            payer_message=data.get("payer_message") or "",
            payee_note=data.get("payee_note") or "",
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except MomoError as exc:
        return jsonify({"error": str(exc), "momo_status": exc.status}), 502
    return jsonify(result), 202


@bp.route("/api/momo/collect/<reference_id>")
@admin_required
def momo_request_status(reference_id):
    try:
        return jsonify(_client().request_status(reference_id))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except MomoError as exc:
        return jsonify({"error": str(exc), "momo_status": exc.status}), 502
