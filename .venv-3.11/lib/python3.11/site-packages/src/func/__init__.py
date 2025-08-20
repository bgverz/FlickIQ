#!/usr/bin/env python3

import click

from .deploy import deploy_app


@click.group()
def func():
    pass


@func.command()
@click.argument("name")
@click.option("--stage", default="dev", help="One of dev or prod.")
def deploy(name, stage):
    deploy_app(stage, name)
