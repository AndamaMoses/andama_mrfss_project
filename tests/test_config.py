"""Phase 1 safety net: config defaults/env overrides and the app factory."""
import os
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
_ENV_KEYS = ("DRUGSHOP_DB", "DRUGSHOP_UPLOADS", "SECRET_KEY", "FLASK_DEBUG")


def _config_defaults(env_overrides):
    env = os.environ.copy()
    for key in _ENV_KEYS:
        env.pop(key, None)
    env.update(env_overrides)
    env["PYTHONIOENCODING"] = "utf-8"
    result = subprocess.run(
        [sys.executable, "-c",
         ("import config;"
          "print(config.DevConfig.SECRET_KEY);"
          "print(config.DevConfig.DATABASE);"
          "print(config.DevConfig.UPLOAD_DIR);"
          "print(config.DevConfig.DEBUG)")],
        cwd=str(PROJECT_ROOT),
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )
    return result.stdout.splitlines()


@pytest.fixture()
def keep_db_globals(monkeypatch):
    """Snapshot db module globals so monkeypatch restores them on teardown."""
    from drugshop import db as dbm

    monkeypatch.setattr(dbm, "_db_path", dbm._db_path)
    monkeypatch.setattr(dbm, "_upload_dir", dbm._upload_dir)


def test_defaults_match_legacy_behavior():
    secret, database, uploads, debug = _config_defaults({})
    assert secret == "drugshop-local-dev-key"
    instance_db = str(PROJECT_ROOT / "instance" / "drugshop.db")
    legacy_db = str(PROJECT_ROOT / "drugshop.db")
    assert database == (instance_db if os.path.exists(instance_db) else legacy_db)
    legacy_uploads = PROJECT_ROOT / "uploads"
    legacy_has_files = legacy_uploads.is_dir() and any(legacy_uploads.iterdir())
    expected_uploads = legacy_uploads if legacy_has_files else PROJECT_ROOT / "instance" / "uploads"
    assert uploads == str(expected_uploads)
    assert debug == "False"


def test_debug_is_opt_in(tmp_path):
    assert _config_defaults({"FLASK_DEBUG": "1"})[3] == "True"


def test_env_overrides_win(tmp_path):
    db_file = tmp_path / "override.db"
    uploads = tmp_path / "uploads"
    secret, database, upload_dir, debug = _config_defaults({
        "DRUGSHOP_DB": str(db_file),
        "DRUGSHOP_UPLOADS": str(uploads),
        "SECRET_KEY": "from-env",
        "FLASK_DEBUG": "0",
    })
    assert secret == "from-env"
    assert database == str(db_file)
    assert upload_dir == str(uploads)
    assert debug == "False"


def test_session_cookie_domain_is_env_optional():
    env = os.environ.copy()
    env.pop("SESSION_COOKIE_DOMAIN", None)
    env["PYTHONIOENCODING"] = "utf-8"
    result = subprocess.run(
        [sys.executable, "-c",
         ("import os, importlib, config;"
          "print(config.BaseConfig.SESSION_COOKIE_DOMAIN);"
          "os.environ['SESSION_COOKIE_DOMAIN']='.example.com';"
          "importlib.reload(config);"
          "print(config.BaseConfig.SESSION_COOKIE_DOMAIN)")],
        cwd=str(PROJECT_ROOT),
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )
    assert result.stdout.splitlines() == ["None", ".example.com"]


def _prod_config_check(env_overrides):
    env = os.environ.copy()
    for key in _ENV_KEYS:
        env.pop(key, None)
    env.update(env_overrides)
    env["PYTHONIOENCODING"] = "utf-8"
    return subprocess.run(
        [sys.executable, "-c",
         ("from config import ProdConfig;"
          "from drugshop import create_app;"
          "create_app(ProdConfig);"
          "print('ok')")],
        cwd=str(PROJECT_ROOT),
        env=env,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def test_prod_config_requires_secret_key(tmp_path):
    paths = {
        "DRUGSHOP_DB": str(tmp_path / "prod.db"),
        "DRUGSHOP_UPLOADS": str(tmp_path / "prod-uploads"),
    }
    missing = _prod_config_check(paths)
    assert missing.returncode != 0
    assert "SECRET_KEY" in missing.stderr

    ready = _prod_config_check({**paths, "SECRET_KEY": "prod-secret"})
    assert ready.returncode == 0, ready.stderr
    assert "ok" in ready.stdout


def test_factory_accepts_config_object(tmp_path, keep_db_globals):
    from drugshop import create_app

    class TestConfig:
        SECRET_KEY = "factory-secret"
        DATABASE = str(tmp_path / "factory.db")
        UPLOAD_DIR = str(tmp_path / "factory-uploads")
        DEBUG = False
        TESTING = True

    app = create_app(TestConfig)
    assert app.config["DATABASE"] == TestConfig.DATABASE
    assert app.config["UPLOAD_DIR"] == TestConfig.UPLOAD_DIR
    assert app.secret_key == "factory-secret"
    assert app.debug is False
    assert app.config["SESSION_COOKIE_HTTPONLY"] is True
    assert app.config["SESSION_COOKIE_SAMESITE"] == "Lax"
    assert Path(TestConfig.UPLOAD_DIR).is_dir()
    assert len(list(app.url_map.iter_rules())) == 56

    client = app.test_client()
    assert client.get("/api/me").status_code == 200
    for page in ("/", "/login", "/staff", "/tender"):
        assert client.get(page).status_code == 200, page
