#!/bin/bash

# This should only be run on develop branch. Builds and releases to pypi.
# Also updates version numbers, creates a release tag, then pushes the new develop and release branches to github.

# Exit if any command fails
set -e

# Show commands executing
set -x

# Bump to new release version
uv run scripts/dev_tools.py bump-version release
RELEASE_TAG=v$(uv run scripts/dev_tools.py version)

# Save tag name to github actions environment
echo "RELEASE_TAG=$RELEASE_TAG" >> "$GITHUB_ENV"

# Build distribution archive.
# These env variables activate hatch build hooks to modify the release
BUNDLE_WEBUI=true BUILD_LOCKED_EXTRAS=true uv build

# Setup git user
git config user.email github-actions[bot]@users.noreply.github.com
git config user.name github-actions[bot]

# Commit and tag released version
git add flexget/_version.py
git commit -m "$RELEASE_TAG"
git tag -a -f "$RELEASE_TAG" -m "$RELEASE_TAG release"

# Bump to new dev version, then commit again
uv run scripts/dev_tools.py bump-version dev
git add flexget/_version.py
git commit -m "Prepare v$(uv run scripts/dev_tools.py version)"

# Automatically merge commits without conflicts
git pull --no-edit
git push origin develop
# Make sure our branches push before pushing tag
git push --tags

# Publish to PyPI after performing `git push` — this prevents the situation where the package has
# already been published to PyPI but the `git push` fails, causing all subsequent runs to fail.
uv publish

# Build changelog
{
  echo 'CHANGELOG_BODY<<EOF'
  uv run scripts/dev_tools.py get-changelog "$RELEASE_TAG"
  echo 'EOF'
} >> "$GITHUB_ENV"

# Export config schema
echo 'tasks: {}' > config.yml
uv run flexget export-schema --output-file flexget-config.schema.json
