#!/usr/bin/env python3

import click

from . import buckets
from . import files


@click.group()
def storage():
    pass


@storage.command()
@click.argument("bucket_name")
def create_bucket(bucket_name):
    buckets.create_bucket(bucket_name=bucket_name)


@storage.command()
@click.argument("bucket_name")
def delete_bucket(bucket_name):
    message = (
        f"Wait! To irreversibly delete bucket {bucket_name}, enter its bucket_name"
    )
    value = click.prompt(message, type=str)
    if value == bucket_name:
        buckets.delete_bucket(bucket_name=bucket_name)


@storage.command()
@click.argument("filename")
@click.option("--bucket", help="The bucket to upload to.")
@click.option("--path", default=None, help="Where to upload the file in the bucket.")
def upload(filename, bucket, path=None):
    if bucket is None:
        raise click.UsageError('Error: Missing option "--bucket".')
    files.upload_file(filename, bucket_name=bucket, path=path)
