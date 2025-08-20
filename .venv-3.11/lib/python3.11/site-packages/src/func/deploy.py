#!/usr/bin/env python3

import sys
import subprocess
import os
import shutil


def install_requirement(url, directory="lib"):
    subprocess.call(["pip", "install", url, "--target", directory])


def install_requirements(directory, filename="private_requirements.txt"):
    if os.path.exists(filename):
        with open(filename) as f:
            for line in f:
                install_requirement(line.strip(), directory)


def remove_requirements_directory(directory="lib"):
    if os.path.exists(directory):
        shutil.rmtree(directory)


def deploy_function(stage, name):
    subprocess.call(
        [
            "gcloud",
            "functions",
            "deploy",
            name,
            "--runtime=python37",
            "--trigger-http",
            "--entry-point=handler",
            f"--env-vars-file=env.{stage}.yaml",
        ]
    )


def deploy_app(stage, name, directory="lib"):
    remove_requirements_directory(directory)
    install_requirements(directory)
    deploy_function(stage, name)
    remove_requirements_directory(directory)
