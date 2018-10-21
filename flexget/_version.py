"""
Current FlexGet version.
This is contained in a separate file so that it can be easily read by setup.py, and easily edited and committed by
release scripts in continuous integration. Should (almost) never be set manually.

The version should always be set to the <next release version>.dev
The jenkins release job will automatically strip the .dev for release,
and update the version again for continued development.
"""
__version__ = '2.17.2'
