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
  python dev_tools.py bump_version release
  export VERSION=`python dev_tools.py version`

  # Package WebUI
  python dev_tools.py bundle_webui

  # Build and upload to pypi.
  python setup.py sdist bdist_wheel --universal
  twine upload dist/*

  # Commit and tag released version
  git add flexget/_version.py
  git commit -m "v${VERSION}"
  git tag -a -f "v${VERSION}" -m "v${VERSION} release"

  # Bump to new dev version, then commit again
  python dev_tools.py bump_version dev
  git add flexget/_version.py
  git commit -m "Prepare v`python dev_tools.py version`"
  git branch -f develop HEAD

  # master branch should be at the release we tagged
  git branch -f master v${VERSION}
  # If either of the new branches are not fast forwards, the push will be rejected
  git push origin master develop
  # Make sure our branches push before pushing tag
  git push --tags
else
  echo "No commits, skipping release"
fi
