#!/usr/bin/env python3

import subprocess


def create_repo(name):
    subprocess.call(["gcloud", "source", "repos", "create", name])
    subprocess.call(["gcloud", "source", "repos", "clone", name])
