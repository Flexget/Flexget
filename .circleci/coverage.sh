#!/bin/bash

# Exit if any command fails
set -e

# Show commands executing
set -x

# Skip if from a PR
if [ -n "${CI_PULL_REQUEST}" ]; then
    exit
fi

# Only run on develop branch
if [ "${CIRCLE_BRANCH}" == "develop" ]; then
    python3 -m venv venv
    . venv/bin/activate
    python-codacy-coverage -r coverage.xml
fi
