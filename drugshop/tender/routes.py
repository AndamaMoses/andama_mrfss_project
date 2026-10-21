"""Tender Copilot routes: page, analyze, history, detail, methodology draft.

Route bodies carried over from app.py (Phase 4.11). The upload directory comes
from the db layer accessor so test/real paths resolve identically.
"""
import json
import os
from datetime import datetime

from flask import Blueprint, jsonify, render_template, request

from drugshop.apps import registry
from drugshop.apps.service import entitled_app_ids_or_all
from drugshop.auth.guards import current_user
from drugshop.core.utils import safe_upload_name
from drugshop.db import execute, q_all, q_one, upload_dir
from drugshop.tender.service import (
    analyze_tender_text,
    draft_methodology,
    extract_pdf_text,
)

bp = Blueprint("tender", __name__)


# ---------- tender copilot ----------
@bp.route("/tender")
def tender_page():
    """Render the Tender Copilot workspace with plan-aware branding.

    A Tender-only installation must not leak the pharmacy brand or its upsell
    paths, while a combined installation keeps a single route back to the
    suite. ``entitled_app_ids_or_all`` fails open until the entitlement
    migration has run, matching the request gate.
    """
    active = entitled_app_ids_or_all()
    pharmacy_active = bool(active & set(registry.PHARMACY_APP_IDS))
    user = current_user()
    return render_template(
        "tender.html",
        standalone="tender" in active and not pharmacy_active,
        show_pharmacy_link=pharmacy_active,
        signed_in=bool(user),
        user_name=(user or {}).get("display_name") or (user or {}).get("username") or "",
    )


@bp.route("/api/tender/analyze", methods=["POST"])
def api_tender_analyze():
    text, filename = "", "pasted-text"
    if request.content_type and "multipart" in request.content_type:
        f = request.files.get("file")
        if not f or not f.filename:
            return jsonify({"error": "PDF file required (field 'file')"}), 400
        # Flatten and whitelist the client-supplied name so the upload can
        # never escape UPLOAD_DIR or smuggle markup into the history table.
        filename = safe_upload_name(f.filename)
        path = os.path.join(upload_dir(), datetime.now().strftime("%Y%m%d_%H%M%S_") + filename)
        f.save(path)
        if filename.lower().endswith(".pdf"):
            try:
                text = extract_pdf_text(path)
            except Exception as e:  # noqa: BLE001
                return jsonify({"error": f"Could not read PDF: {e}. Install pypdf or paste text instead."}), 400
        else:
            with open(path, encoding="utf-8", errors="ignore") as fh:
                text = fh.read()[:60000]
    else:
        d = request.json or {}
        text = (d.get("text") or "")[:60000]
        filename = d.get("filename", "pasted-text")
    if not text.strip():
        return jsonify({"error": "No text found. Scanned PDFs need OCR — paste the tender text instead."}), 400
    matrix, risks, score = analyze_tender_text(text)
    lid = execute("INSERT INTO tender_docs(filename,text_len,text_excerpt,compliance_json,risks_json,score) VALUES(?,?,?,?,?,?)",
                  (filename, len(text), text[:800], json.dumps(matrix), json.dumps(risks), score))
    return jsonify({"id": lid, "filename": filename, "score": score, "matrix": matrix, "risks": risks,
                    "found": sum(1 for m in matrix if m["status"] == "FOUND"), "total": len(matrix)}), 201


@bp.route("/api/tender/list")
def api_tender_list():
    rows = q_all("SELECT id, filename, uploaded_at, text_len, score FROM tender_docs ORDER BY id DESC LIMIT 50")
    return jsonify(rows)


@bp.route("/api/tender/<int:tid>")
def api_tender_one(tid):
    r = q_one("SELECT * FROM tender_docs WHERE id=?", (tid,))
    if not r:
        return jsonify({"error": "not found"}), 404
    r["matrix"] = json.loads(r.get("compliance_json") or "[]")
    r["risks"] = json.loads(r.get("risks_json") or "[]")
    return jsonify(r)


@bp.route("/api/tender/methodology", methods=["POST"])
def api_tender_methodology():
    d = request.json or {}
    return jsonify({"methodology": draft_methodology(d)})
