#!/usr/bin/env python3

import subprocess

from .helpers import with_bucket_name


@with_bucket_name
def upload_file(filename, bucket_name, path):
    bucket_path = bucket_name if path is None else bucket_name + path
    try:
        subprocess.check_call(["gsutil", "cp", filename, bucket_path])
    except subprocess.CalledProcessError:
        pass
    else:
        print("Success!")
