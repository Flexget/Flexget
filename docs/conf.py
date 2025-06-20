import os
import sys
from pathlib import Path

from sphinx.util import logging

logger = logging.getLogger(__name__)
sys.path.append(str(Path.cwd()))

# -- General configuration ---------------------------------------------------

extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.doctest',
    'sphinx.ext.intersphinx',
    'sphinx.ext.viewcode',
    'sphinx_copybutton',
    'sphinx_design',
    '_extensions.gallery_directive',
]
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']
suppress_warnings = ['config.cache']
nitpicky = False  # TODO: Enable after https://github.com/sphinx-doc/sphinx/issues/11991

# -- sphinx.ext.autodoc options ----------------------------------------------

autodoc_default_options = {
    'members': True,
    'undoc-members': True,
    'private-members': True,
    'show-inheritance': True,
}
autodoc_member_order = 'groupwise'
autodoc_typehints = 'description'
autodoc_mock_imports = ['guppy']

# -- sphinx.ext.intersphinx options ------------------------------------------

intersphinx_mapping = {
    'flask': ('https://flask.palletsprojects.com/en/stable', None),
    'flask-restx': ('https://flask-restx.readthedocs.io/en/stable', None),
    'jsonschema': ('https://python-jsonschema.readthedocs.io/en/stable', None),
    'loguru': ('https://loguru.readthedocs.io/en/stable', None),
    'python': ('https://docs.python.org/3', None),
    'python-telegram-bot': ('https://docs.python-telegram-bot.org/en/stable', None),
    'requests': ('https://requests.readthedocs.io/en/stable', None),
    'rich': ('https://rich.readthedocs.io/en/stable/', None),
    'sqlalchemy': ('https://docs.sqlalchemy.org', None),
    'transmission-rpc': ('https://transmission-rpc.readthedocs.io/en/stable', None),
}

# -- sphinx_copybutton options -----------------------------------------------

copybutton_exclude = '.linenos, .gp, .go'

# -- Options for HTML output -------------------------------------------------


def _custom_edit_url(file_name: str) -> str:
    file_path = 'docs/' + file_name
    if file_name.startswith('api/'):
        modpath = Path(file_name.removeprefix('api/').removesuffix('.rst').replace('.', '/'))
        modpath_parent = Path.cwd().parent
        if (modpath_parent / modpath).is_dir():
            file_path = modpath / '__init__.py'
        elif (modpath_parent / (modpath.with_suffix('.py'))).is_file():
            file_path = modpath.with_suffix('.py')
        else:
            logger.warning('Unknown type, unable to generate the URL for: %s.', file_name)
    return f'https://github.com/flexget/flexget/edit/develop/{file_path}'


html_theme = 'pydata_sphinx_theme'
html_static_path = ['_static']
html_css_files = ['custom.css']
html_js_files = ['custom-icon.js']
html_favicon = '_static/logo.svg'
html_logo = '_static/logo.png'
html_show_sourcelink = False
html_theme_options = {
    'switcher': {
        'json_url': 'https://flexget.readthedocs.io/en/latest/_static/switcher.json',
        'version_match': os.environ.get('READTHEDOCS_VERSION'),
    },
    'external_links': [
        {
            'url': 'https://flexget.com',
            'name': 'User guide',
        },
    ],
    'icon_links': [
        {
            'name': 'GitHub',
            'url': 'https://github.com/flexget/flexget',
            'icon': 'fa-brands fa-github',
        },
        {
            'name': 'PyPI',
            'url': 'https://pypi.org/project/flexget',
            'icon': 'fa-custom fa-pypi',
        },
        {
            'name': 'Docker',
            'url': 'https://hub.docker.com/r/flexget/flexget',
            'icon': 'fa-brands fa-docker',
        },
    ],
    'navbar_center': ['version-switcher', 'navbar-nav'],
    'show_toc_level': 2,
    'use_edit_page_button': True,
    'footer_start': [],
    'footer_end': [],
}
html_context = {
    'edit_page_url_template': '{{ custom_edit_url(file_name) }}',
    'custom_edit_url': _custom_edit_url,
    'edit_page_provider_name': 'GitHub',
}
