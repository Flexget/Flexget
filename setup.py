from __future__ import print_function
import io
import sys

from setuptools import setup, find_packages


install_requires = [
    'FeedParser>=5.2.1',
    # There is a bug in sqlalchemy 0.9.0, see gh#127
    'SQLAlchemy >=0.7.5, !=0.9.0, <1.999',
    'PyYAML',
    # There is a bug in beautifulsoup 4.2.0 that breaks imdb parsing, see http://flexget.com/ticket/2091
    'beautifulsoup4>=4.1, !=4.2.0, <4.5',
    'html5lib>=0.11',
    'PyRSS2Gen',
    'pynzb',
    'progressbar',
    'rpyc',
    'jinja2',
    # There is a bug in requests 2.4.0 where it leaks urllib3 exceptions
    'requests>=1.0, !=2.4.0, <2.99',
    'python-dateutil!=2.0, !=2.2',
    'jsonschema>=2.0',
    'tmdb3',
    'path.py',
    'guessit>=2.0.3',
    'apscheduler',
    'pytvmaze>=1.4.5',
    'ordereddict>=1.1',
    # WebUI Requirements
    'cherrypy>=3.7.0',
    'flask>=0.7',
    'flask-restful>=0.3.3',
    'flask-restplus==0.8.6',
    'flask-compress>=1.2.1',
    'flask-login>=0.3.2',
    'flask-cors>=2.1.2',
    'pyparsing>=2.0.3',
    'Safe'
]

extras_require = {
    ':python_version=="2.6"': ['argparse']
}

entry_points = {'console_scripts': ['flexget = flexget:main']}

# Provide an alternate exe on windows which does not cause a pop-up when scheduled
if sys.platform.startswith('win'):
    entry_points.setdefault('gui_scripts', []).append('flexget-headless = flexget:main')

with io.open('README.rst', encoding='utf-8') as readme:
    long_description = readme.read()

# Populates __version__ without importing the package
__version__ = None
execfile('flexget/_version.py')
if not __version__:
    print('Could not find __version__ from flexget/_version.py')
    sys.exit(1)

setup(
    name='FlexGet',
    version=__version__,  # release task may edit this
    description='FlexGet is a program aimed to automate downloading or processing content (torrents, podcasts, etc.) '
                'from different sources like RSS-feeds, html-pages, various sites and more.',
    long_description=long_description,
    author='Marko Koivusalo',
    author_email='marko.koivusalo@gmail.com',
    license='MIT',
    url='http://flexget.com',
    download_url='http://download.flexget.com',
    install_requires=install_requires,
    packages=find_packages(exclude=['tests']),
    include_package_data=True,
    zip_safe=False,
    test_suite='nose.collector',
    extras_require={
        'memusage': ['guppy'],
        'NZB': ['pynzb'],
        'TaskTray': ['pywin32'],
    },
    entry_points=entry_points,
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python",
        "Programming Language :: Python :: 2",
        "Programming Language :: Python :: 2.6",
        "Programming Language :: Python :: 2.7",
        "Programming Language :: Python :: Implementation :: CPython",
        "Programming Language :: Python :: Implementation :: PyPy",
    ]

)
