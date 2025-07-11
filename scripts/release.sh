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
if [ -z "$(git tag --points-at HEAD)" ] && [ -z "$(git tag --points-at HEAD~1)" ]; then

  # Bump to new release version
  uv run scripts/dev_tools.py bump-version release
  VERSION=$(uv run scripts/dev_tools.py version)
  export VERSION

  # Build and upload to pypi.
  # These env variables activate hatch build hooks to modify the release
  BUNDLE_WEBUI=true BUILD_LOCKED_EXTRAS=true uv build
  uv publish

  # Commit and tag released version
  git add flexget/_version.py
  git commit -m "v${VERSION}"
  git tag -a -f "v${VERSION}" -m "v${VERSION} release"

  # Save tag name to github actions environment
  echo "release_tag=v${VERSION}" >> $GITHUB_ENV

  # Bump to new dev version, then commit again
  uv run scripts/dev_tools.py bump-version dev
  git add flexget/_version.py
  git commit -m "Prepare v$(uv run scripts/dev_tools.py version)"

  # If the new branch is not a fast-forward, the push will be rejected
  git push origin develop
  # Make sure our branches push before pushing tag
  git push --tags
else
  echo "No commits, skipping release"
fi
