import io
import os

from drugshop.db import upload_dir
from drugshop.tender.service import analyze_tender_text, extract_pdf_text

TENDER_TEXT = (
    "Invitation to bid: construction of access roads. "
    "Bidders must submit a bid security of 2% and a valid PPDA registration certificate. "
    "Tax clearance certificate from URA and NSSF clearance are required. "
    "Power of attorney for the signatory. Equipment schedule and key personnel CVs "
    "with academic certificates shall be submitted. Audited accounts for 3 years. "
    "Work programme and methodology are part of the evaluation. "
    "A site visit is mandatory. Performance security of 10%. "
    "Deadline for submission: 15 November 2026 at 11:00am."
)


def test_tender_requires_login(client):
    r = client.post("/api/tender/analyze", json={"text": TENDER_TEXT})
    assert r.status_code == 401


def test_analyze_text_builds_matrix(admin_client):
    r = admin_client.post("/api/tender/analyze", json={"text": TENDER_TEXT, "filename": "notice.txt"})
    assert r.status_code == 201
    j = r.get_json()
    assert j["total"] == 14
    assert j["score"] > 0
    found = {m["id"] for m in j["matrix"] if m["status"] == "FOUND"}
    assert {"bid_security", "ppda_cert", "tax_clearance", "nssf", "site_visit"} <= found
    assert j["risks"]


def test_analyze_empty_text_400(admin_client):
    r = admin_client.post("/api/tender/analyze", json={"text": "   "})
    assert r.status_code == 400


def test_tender_history_list_and_detail(admin_client):
    admin_client.post("/api/tender/analyze", json={"text": TENDER_TEXT, "filename": "hist.txt"})
    rows = admin_client.get("/api/tender/list").get_json()
    assert rows and rows[0]["filename"] == "hist.txt"
    detail = admin_client.get(f"/api/tender/{rows[0]['id']}").get_json()
    assert detail["matrix"]
    assert detail["risks"]


def test_tender_detail_missing_404(admin_client):
    assert admin_client.get("/api/tender/99999").status_code == 404


def test_analyze_multipart_text_upload(admin_client):
    r = admin_client.post("/api/tender/analyze", data={
        "file": (io.BytesIO(TENDER_TEXT.encode("utf-8")), "notice copy.txt"),
    })
    assert r.status_code == 201
    j = r.get_json()
    assert j["filename"] == "notice_copy.txt"
    assert j["total"] == 14


def test_analyze_multipart_pdf_uses_extractor(admin_client, monkeypatch):
    captured = {}

    def fake_extract(path):
        captured["path"] = path
        return TENDER_TEXT

    monkeypatch.setattr("drugshop.tender.routes.extract_pdf_text", fake_extract)
    r = admin_client.post("/api/tender/analyze", data={
        "file": (io.BytesIO(b"%PDF-1.4 fake"), "scan.pdf"),
    })
    assert r.status_code == 201
    assert r.get_json()["filename"] == "scan.pdf"
    assert os.path.dirname(captured["path"]) == upload_dir()
    assert os.path.basename(captured["path"]).endswith("_scan.pdf")
    assert os.path.exists(captured["path"])


def test_analyze_upload_filename_cannot_escape_upload_dir(admin_client, monkeypatch):
    captured = {}

    def fake_extract(path):
        captured["path"] = path
        return TENDER_TEXT

    monkeypatch.setattr("drugshop.tender.routes.extract_pdf_text", fake_extract)
    r = admin_client.post("/api/tender/analyze", data={
        "file": (io.BytesIO(b"%PDF-1.4 fake"), "../../evil.pdf"),
    })
    assert r.status_code == 201
    assert os.path.dirname(captured["path"]) == upload_dir()
    assert os.path.basename(captured["path"]).endswith("_evil.pdf")


def test_analyze_empty_service_scores_zero():
    matrix, risks, score = analyze_tender_text("")
    assert len(matrix) == 14
    assert score == 0
    assert all(m["status"] == "MISSING" for m in matrix)
    assert any(r["level"] == "HIGH" for r in risks)


def test_extract_pdf_text_enforces_page_and_char_limits(monkeypatch):
    import pypdf

    class FakePage:
        def __init__(self, text):
            self._text = text

        def extract_text(self):
            return self._text

    class FakeReader:
        def __init__(self, path):
            self.pages = [FakePage(f"PAGE{i}") for i in range(100)]

    monkeypatch.setattr(pypdf, "PdfReader", FakeReader)
    text = extract_pdf_text("fake.pdf", max_chars=10**9)
    assert "PAGE0" in text and "PAGE79" in text
    assert "PAGE80" not in text
    assert len(text.split("\n")) == 80

    assert len(extract_pdf_text("fake.pdf", max_chars=100)) == 100


def test_analyze_bad_pdf_returns_400(admin_client, monkeypatch):
    def boom(path):
        raise ValueError("bad pdf")

    monkeypatch.setattr("drugshop.tender.routes.extract_pdf_text", boom)
    r = admin_client.post("/api/tender/analyze", data={
        "file": (io.BytesIO(b"%PDF-1.4 fake"), "broken.pdf"),
    })
    assert r.status_code == 400
    assert "Could not read PDF" in r.get_json()["error"]


def test_tender_methodology_draft(admin_client):
    r = admin_client.post("/api/tender/methodology", json={
        "project_name": "Jinja Roads", "client": "MOWT", "location": "Jinja",
        "duration_weeks": "12", "scope_summary": "road works",
    })
    assert r.status_code == 200
    text = r.get_json()["methodology"]
    assert "TECHNICAL METHODOLOGY" in text
    assert "Jinja Roads" in text
    assert "Communion Engineering Services Ltd" in text
