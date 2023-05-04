"""
Current FlexGet version.
This is contained in a separate file so that it can be easily read by setuptools, and easily edited and committed by
release scripts in continuous integration. Should only need to be set manually when doing a major/minor version bump.

The version should always be set to the <next release version>.dev
The github actions release job will automatically strip the .dev for release,
and update the version again for continued development.
"""
__version__ = '3.6.7'
