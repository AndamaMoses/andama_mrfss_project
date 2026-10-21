import sqlite3

from werkzeug.security import check_password_hash

db = sqlite3.connect('drugshop.db')
h = db.execute("SELECT pass_hash FROM users WHERE username='admin'").fetchone()[0]
for pw in ['admin123', 'admin', 'password', '123456', 'Admin123', 'admin123 ']:
    try:
        ok = check_password_hash(h, pw)
    except Exception as e:  # noqa: BLE001
        ok = f'ERR {e}'
    print(repr(pw), '->', ok)
