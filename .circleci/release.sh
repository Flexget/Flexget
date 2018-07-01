#!/bin/bash

# Exit if any command fails
set -e

# Show commands executing
set -x

# Only run if there are new commits
if git log --skip 1 origin/master..origin/develop|grep '^commit '; then
  # Activate virtual env
  . venv/bin/activate

  # Bump to new release version
  python dev_tools.py bump_version release
  export VERSION=`python dev_tools.py version`

  # Package WebUI
  python dev_tools.py bundle_webui

  # Build and upload to pypi.
  python setup.py sdist bdist_wheel --universal
  twine upload dist/*

  # We are working on a detached head, we'll point the branches to the right commits at the end
  # Commit and tag released version
  git add flexget/_version.py
  git commit -m "v${VERSION}"
  git tag -a -f "${VERSION}" -m "${VERSION} release"

  # Bump to new dev version, then commit again
  python dev_tools.py bump_version dev
  git add flexget/_version.py
  git commit -m "Prepare v`python dev_tools.py version`"

  # master branch should be at the release we tagged
  git branch -f master ${VERSION}
  # If either of the new branches are not fast forwards, the push will be rejected
  git push origin master develop
  # Make sure our branches push before pushing tag
  git push --tags
else
  echo "No commits, skipping release"
fi