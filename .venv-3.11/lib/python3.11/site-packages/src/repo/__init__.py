#!/usr/bin/env python3

import click

from .create import create_repo


@click.group()
def repo():
    pass


@repo.command()
@click.argument("name")
def create(name):
    create_repo(name)
