"""Auth CLI: lockout recovery without a running server.

Use when nobody can sign in (for example the last admin password is lost):

    flask --app run reset-password admin
"""
import click
from werkzeug.security import generate_password_hash

from drugshop.db import execute, q_one

MIN_PASSWORD_LEN = 6


@click.command("reset-password")
@click.argument("username")
@click.option(
    "--password",
    prompt=True,
    hide_input=True,
    confirmation_prompt=True,
    help="New password (prompted twice when omitted).",
)
def reset_password_command(username, password):
    """Reset the password for USERNAME (case-insensitive)."""
    if len(password) < MIN_PASSWORD_LEN:
        raise click.ClickException(f"password must be {MIN_PASSWORD_LEN}+ characters")
    user = q_one("SELECT id, username FROM users WHERE LOWER(username)=LOWER(?)",
                 (username.strip(),))
    if not user:
        raise click.ClickException(f"no user named '{username}'")
    execute("UPDATE users SET pass_hash=? WHERE id=?",
            (generate_password_hash(password), user["id"]))
    click.echo(f"Password updated for {user['username']}. "
               "Share it privately and change it after signing in.")


def register_cli(app):
    app.cli.add_command(reset_password_command)
