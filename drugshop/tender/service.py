"""Tender Copilot service: PPDA requirement matrix, PDF ingest, methodology.

Functions carried over verbatim from app.py (Phase 4.11). ``extract_pdf_text``
keeps its 80-page / 60k-character limits, and ``analyze_tender_text`` keeps the
exact keyword scan, scoring, and risk rules.
"""

PPDA_REQUIREMENTS = [
    {"id": "bid_security", "label": "Bid Security / Bid-Securing Declaration", "keywords": ["bid security", "bid-securing", "bid bond", "bank guarantee"]},
    {"id": "ppda_cert", "label": "Valid PPDA Registration Certificate", "keywords": ["ppda", "registration certificate", "provider registration"]},
    {"id": "trading_licence", "label": "Valid Trading Licence", "keywords": ["trading licence", "trading license", "business licence"]},
    {"id": "tax_clearance", "label": "Tax Clearance Certificate (URA)", "keywords": ["tax clearance", "ura", "tin certificate"]},
    {"id": "nssf", "label": "NSSF Clearance Certificate", "keywords": ["nssf", "social security"]},
    {"id": "power_attorney", "label": "Power of Attorney", "keywords": ["power of attorney"]},
    {"id": "experience", "label": "Specific Experience & Completion Certificates", "keywords": ["completion certificate", "specific experience", "similar works", "reference letters"]},
    {"id": "equipment", "label": "Equipment Schedule + Ownership/Lease Proof", "keywords": ["equipment schedule", "equipment list", "logbook", "lease agreement"]},
    {"id": "personnel", "label": "Key Personnel CVs + Academic Certificates", "keywords": ["curriculum vitae", "cv of", "key personnel", "academic certificates", "engineer registration", "erb"]},
    {"id": "audited", "label": "Audited Accounts (3 years)", "keywords": ["audited accounts", "financial statements", "auditor"]},
    {"id": "work_programme", "label": "Work Programme / Methodology", "keywords": ["work programme", "work program", "methodology", "execution programme"]},
    {"id": "site_visit", "label": "Site Visit Certificate / Pre-bid Meeting", "keywords": ["site visit", "pre-bid", "pre bid meeting"]},
    {"id": "performance_security", "label": "Performance Security Terms", "keywords": ["performance security", "performance guarantee"]},
    {"id": "declaration", "label": "Declaration of Non-Blacklisting / Code of Ethics", "keywords": ["blacklist", "code of ethical conduct", "declaration form"]},
]


def extract_pdf_text(path, max_chars=60000):
    try:
        from pypdf import PdfReader
    except ImportError:
        from PyPDF2 import PdfReader
    reader = PdfReader(path)
    parts = []
    for pg in reader.pages[:80]:
        try:
            page_text = pg.extract_text() or ""
        except Exception:  # noqa: BLE001
            page_text = None
        if page_text is None:
            continue
        parts.append(page_text)
        if sum(len(p) for p in parts) > max_chars:
            break
    return "\n".join(parts)[:max_chars]


def analyze_tender_text(text):
    low = (text or "").lower()
    matrix = []
    for req in PPDA_REQUIREMENTS:
        hits = [k for k in req["keywords"] if k in low]
        idx = min([low.find(k) for k in hits]) if hits else -1
        snippet = ""
        if idx >= 0 and text:
            s = max(0, idx - 120)
            snippet = text[s:idx + 200].replace("\n", " ")[:320]
        matrix.append({"id": req["id"], "label": req["label"],
                       "status": "FOUND" if hits else "MISSING",
                       "matched": hits, "snippet": snippet})
    found = sum(1 for m in matrix if m["status"] == "FOUND")
    score = round(100 * found / len(matrix), 1) if matrix else 0
    risks = []
    if score < 60:
        risks.append({"level": "HIGH", "risk": "Low compliance visibility — many mandatory items not detected. Verify PDF text extracted fully (scanned images need OCR)."})
    for m in matrix:
        if m["status"] == "MISSING" and m["id"] in ("bid_security", "ppda_cert", "tax_clearance", "performance_security"):
            risks.append({"level": "HIGH", "risk": f"Missing: {m['label']} — bid may be ruled non-responsive."})
    import re
    m_dead = re.search(r"(deadline|submission|closing)[^\n]{0,120}", low)
    if m_dead:
        risks.append({"level": "MEDIUM", "risk": "Check submission deadline & delivery location: ..." + (m_dead.group(0)[:140])})
    else:
        risks.append({"level": "MEDIUM", "risk": "No submission deadline detected in extracted text — confirm in the tender notice."})
    if len(text or "") < 1500:
        risks.append({"level": "MEDIUM", "risk": "Very little text extracted — PDF may be scanned images. Re-upload a searchable PDF or paste the text manually."})
    if "unra" in low or "road" in low:
        risks.append({"level": "INFO", "risk": "UNRA/road works detected — ensure equipment schedule (grader, roller, tipper) + materials lab + survey team are evidenced."})
    if not risks:
        risks.append({"level": "INFO", "risk": "No major red flags detected by keyword scan. Manual review still required."})
    return matrix, risks, score


def draft_methodology(d):
    proj = d.get("project_name", "Proposed Works")
    client = d.get("client", "the Employer")
    loc = d.get("location", "Jinja")
    weeks = d.get("duration_weeks", "12")
    scope = d.get("scope_summary", "general construction works as per drawings and specifications")
    equip = d.get("equipment", "grader, roller, tipper trucks, concrete mixer, survey set")
    team = d.get("team", "Site Agent, Foreman, Surveyor, Lab Technician, HSE Officer")
    return f"""TECHNICAL METHODOLOGY — {proj}
Contractor: Communion Engineering Services Ltd, Jinja | Client: {client}

1. UNDERSTANDING OF THE ASSIGNMENT
We have reviewed the tender drawings, specifications and Bills of Quantities. The works comprise {scope} at {loc}. Our approach prioritises early mobilisation, setting-out verification, and a 4-hour internal approval loop so site milestones are signed off via WhatsApp with photo evidence.

2. MOBILISATION (Week 1)
- Site camp, storage and signage; verify benchmarks with survey set.
- Deploy equipment: {equip}.
- Deploy key team: {team}.
- Submit work programme, HSE plan and QA plan for approval.

3. EXECUTION (Weeks 2-{weeks})
- Setting out → earthworks/structures → finishes, supervised daily by the Site Agent.
- Materials tested per specification; failed lots rejected and re-ordered within 48h.
- Weekly progress photos + milestone sign-off sheets shared with the client.

4. QUALITY ASSURANCE
- Three-tier check: foreman → site agent → director before any milestone sign-off.
- Lab tests (compaction, concrete cubes) filed with each payment certificate.

5. HEALTH, SAFETY & ENVIRONMENT
- PPE, first-aid kit, toolbox talks every Monday; dust/noise control for neighbours; waste disposed at approved sites.

6. PROGRAMME & COMPLETION
- {weeks}-week programme with 10% time contingency; snag list closed within 7 days of substantial completion; 6-month defects liability support.

7. DECLARATION
We confirm availability of the listed personnel and equipment and compliance with PPDA requirements. Prepared by Communion Engineering Services Ltd.
"""
