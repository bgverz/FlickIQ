#!/usr/bin/env python3

import click

from .func import func
from .repo import repo
from .storage import storage


@click.group()
def cli():
    pass


cli.add_command(func)
cli.add_command(repo)
cli.add_command(storage)
