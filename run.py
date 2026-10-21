"""Single entry point: python run.py

The Flask app is built by the application factory in ``drugshop/``; ``app`` is
exposed at module level so ``flask --app run`` keeps working. Database
initialization stays explicit (under ``__main__``) as before the cut-over.
"""
from drugshop import create_app
from drugshop.auth.service import ensure_admin
from drugshop.db import init_db

app = create_app()

if __name__ == "__main__":
    init_db()
    ensure_admin()
    print("Drug shop -> http://127.0.0.1:5000  |  Tender Copilot -> http://127.0.0.1:5000/tender")
    app.run(debug=app.config["DEBUG"])
