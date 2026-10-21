"""Operator CLI for the app plan (Phase 1).

Writes are deliberately operator-only: at 20 customers, self-service
activation is a revenue leak and a support risk. The customer sees a read-only
plan panel; the operator runs, after payment:

    flask --app run plan show
    flask --app run plan set pro --expires 2027-10-21 --actor "Andama"
    flask --app run plan add alerts --actor "Andama"
    flask --app run plan remove alerts --actor "Andama"
"""
import sqlite3

import click

from drugshop.apps import registry, service


def _plan_lines():
    plan = service.current_plan()
    rows = service.entitlement_rows()
    yield f"Plan:    {plan['label']}"
    yield f"Expires: {plan['expires_at'] or 'no expiry'}"
    if plan["bootstrap"]:
        yield "Note:    unseeded - all apps are currently allowed (run `python run.py` once)"
    yield "Apps:"
    for app_id in registry.app_ids():
        app = registry.APPS[app_id]
        row = next((r for r in rows if r["app_id"] == app_id), None)
        if app["always_on"]:
            mark, note = "[x]", "always on"
        elif row and row["status"] == "active":
            mark, note = "[x]", f"bundle={row['bundle'] or '-'}"
        elif row:
            mark, note = "[ ]", "revoked"
        else:
            mark, note = "[ ]", "not included"
        yield f"  {mark} {app_id:<10} {app['name']:<22} {note}"


def register_cli(app):
    @app.cli.group("plan")
    def plan_group():
        """Show or change this installation's app plan."""

    @plan_group.command("show")
    def plan_show():
        try:
            lines = list(_plan_lines())
            recent = service.events(10)
        except sqlite3.Error as exc:
            raise click.ClickException(
                "database not initialized - run `python run.py` once, then retry"
            ) from exc
        for line in lines:
            click.echo(line)
        if recent:
            click.echo("Recent changes:")
            for event in recent:
                click.echo(
                    f"  {event['created_at']}  {event['action']:<6} "
                    f"{event['app_id']:<10} {event['actor']} {event['detail']}"
                )

    @plan_group.command("set")
    @click.argument("bundle")
    @click.option("--expires", default=None, help="ISO date (YYYY-MM-DD), informational")
    @click.option("--actor", default="", help="who made the change")
    @click.option("--notes", default="", help="free-text note stored with the event")
    def plan_set(bundle, expires, actor, notes):
        """Set the plan to BUNDLE (core | pro | growth | tender | legacy)."""
        try:
            result = service.set_bundle(
                bundle, expires_at=expires, actor=actor, notes=notes
            )
        except (ValueError, sqlite3.Error) as exc:
            raise click.ClickException(str(exc)) from exc
        click.echo(f"{result['label']} active: {', '.join(result['active'])}")
        for label, key in (("added", "added"), ("changed", "changed"), ("revoked", "removed")):
            if result[key]:
                click.echo(f"  {label}: {', '.join(result[key])}")

    @plan_group.command("add")
    @click.argument("app_id")
    @click.option("--expires", default=None, help="ISO date (YYYY-MM-DD), informational")
    @click.option("--actor", default="", help="who made the change")
    @click.option("--notes", default="", help="free-text note stored with the event")
    def plan_add(app_id, expires, actor, notes):
        """Activate a single add-on app (APP_ID)."""
        try:
            result = service.add_app(
                app_id, expires_at=expires, actor=actor, notes=notes
            )
        except (ValueError, sqlite3.Error) as exc:
            raise click.ClickException(str(exc)) from exc
        click.echo(f"{result['app']}: {result['note']}")

    @plan_group.command("remove")
    @click.argument("app_id")
    @click.option("--actor", default="", help="who made the change")
    @click.option("--notes", default="", help="free-text note stored with the event")
    def plan_remove(app_id, actor, notes):
        """Revoke a single add-on app (APP_ID)."""
        try:
            result = service.remove_app(app_id, actor=actor, notes=notes)
        except (ValueError, sqlite3.Error) as exc:
            raise click.ClickException(str(exc)) from exc
        click.echo(f"{result['app']}: {result['note']}")
