"""MoMo operator CLI.

flask --app run momo status
flask --app run momo status --check
flask --app run momo provision --save
flask --app run momo collect --amount 5000 --phone 0772123456 --external-id SALE-12
flask --app run momo request <reference-id>
"""

import os

import click
from flask import current_app

from config import PROJECT_ROOT
from drugshop.payments.momo import (
    MomoClient,
    MomoError,
    MomoSettings,
    create_api_key,
    create_api_user,
)

ENV_PATH = os.path.join(PROJECT_ROOT, ".env")


def _settings():
    return MomoSettings.from_mapping(current_app.config)


def _update_env(path, values):
    """Update ``KEY=value`` lines in ``.env`` without disturbing the rest."""
    lines = []
    if os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            lines = fh.read().splitlines()
    seen = set()
    out = []
    for line in lines:
        key = line.split("=", 1)[0].strip()
        if key in values:
            out.append(f"{key}={values[key]}")
            seen.add(key)
        else:
            out.append(line)
    for key, value in values.items():
        if key not in seen:
            out.append(f"{key}={value}")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(out).rstrip() + "\n")


@click.group("momo")
def momo_group():
    """MTN MoMo Collections setup and checks."""


@momo_group.command("status")
@click.option("--check", is_flag=True, help="call MTN for a fresh access token")
def momo_status(check):
    """Show configuration and, with --check, prove the token exchange."""
    settings = _settings()
    for key, value in settings.status_payload.items():
        click.echo(f"{key:<20} {value}")
    if not check:
        return
    if not settings.configured:
        raise click.ClickException(
            "MoMo credentials are incomplete - see `momo provision --save`"
        )
    try:
        MomoClient(settings).access_token()
    except MomoError as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo("token                OK (MTN accepted the credentials)")


@momo_group.command("provision")
@click.option(
    "--callback-host",
    default="localhost",
    show_default=True,
    help="Host MTN may call back (no scheme or path).",
)
@click.option("--save", is_flag=True, help="write the API user/key into .env")
def momo_provision(callback_host, save):
    """Create an API user + API key for the configured environment."""
    settings = _settings()
    if not settings.subscription_key:
        raise click.ClickException(
            "MOMO_SUBSCRIPTION_KEY is not set - add it to .env first"
        )
    click.echo(f"environment          {settings.environment}")
    click.echo(f"base_url             {settings.resolved_base_url}")
    try:
        api_user = create_api_user(settings, callback_host=callback_host)
        api_key = create_api_key(settings, api_user)
    except MomoError as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo(f"api_user             {api_user}")
    click.echo(f"api_key              {api_key}")
    if save:
        _update_env(ENV_PATH, {"MOMO_API_USER": api_user, "MOMO_API_KEY": api_key})
        click.echo(f"saved to             {os.path.relpath(ENV_PATH)}")
    else:
        click.echo("Add both values to .env, then run `momo status --check`.")
    click.echo("Note: the customer must approve the prompt on their phone;")
    click.echo("      a 202 response means 'request accepted', not 'paid'.")


@momo_group.command("collect")
@click.option("--amount", required=True, type=float, help="Amount in shop currency.")
@click.option("--phone", required=True, help="Customer MSISDN, e.g. 0772123456.")
@click.option("--external-id", default="manual", show_default=True)
@click.option("--reference-id", default=None, help="Reuse an existing reference id.")
def momo_collect(amount, phone, external_id, reference_id):
    """Ask MTN to push a payment prompt to a customer's phone."""
    settings = _settings()
    if not settings.configured:
        raise click.ClickException(
            "MoMo credentials are incomplete - run `momo provision --save`"
        )
    try:
        result = MomoClient(settings).request_to_pay(
            amount=amount,
            phone=phone,
            external_id=external_id,
            reference_id=reference_id,
        )
    except (MomoError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo(f"reference_id         {result['reference_id']}")
    click.echo(f"payer                {result['payer']['partyId']}")
    click.echo(f"amount               {result['amount']} {result['currency']}")
    click.echo("The customer must approve the prompt; then run `momo request <id>`.")


@momo_group.command("request")
@click.argument("reference_id")
def momo_request(reference_id):
    """Show the status of a collection request."""
    settings = _settings()
    if not settings.configured:
        raise click.ClickException(
            "MoMo credentials are incomplete - run `momo provision --save`"
        )
    try:
        data = MomoClient(settings).request_status(reference_id)
    except (MomoError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc
    for key, value in (data or {}).items():
        click.echo(f"{key:<20} {value}")


def register_cli(app):
    app.cli.add_command(momo_group)
