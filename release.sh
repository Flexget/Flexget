#!/bin/bash

# This should only be run on develop branch. Builds and releases to pypi.
# Also updates version numbers, creates a release tag, then pushes the new develop and release branches to github.

# Exit if any command fails
set -e

# Show commands executing
set -x

# Error if running on a branch other than develop
if [ "$(git rev-parse HEAD)" != "$(git rev-parse origin/develop)" ]; then
  echo "Release script should be run from develop branch."
  exit 1
fi

# Only run if there are new commits
if git log --skip 1 origin/master..origin/develop|grep '^commit '; then

  # Bump to new release version
  uv run --no-project dev_tools.py bump-version release
  export VERSION=$(uv run --no-project dev_tools.py version)
  uv lock --upgrade-package flexget

  # Package WebUI
  uv run dev_tools.py bundle-webui

  # Build and upload to pypi.
  uv build
  uv publish

  # Commit and tag released version
  git add flexget/_version.py
  git add uv.lock
  git commit -m "v${VERSION}"
  git tag -a -f "v${VERSION}" -m "v${VERSION} release"

  # Save tag name to github actions environment
  echo "release_tag=v${VERSION}" >> $GITHUB_ENV

  # Bump to new dev version, then commit again
  uv run --no-project dev_tools.py bump-version dev
  uv lock --upgrade-package flexget
  git add flexget/_version.py
  git add uv.lock
  git commit -m "Prepare v$(uv run --no-project dev_tools.py version)"

  # master branch should be at the release we tagged
  git branch -f master v${VERSION}
  # If either of the new branches are not fast forwards, the push will be rejected
  git push origin master develop
  # Make sure our branches push before pushing tag
  git push --tags
else
  echo "No commits, skipping release"
fi
