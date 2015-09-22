"""
FlexGet build and development utilities - unfortunately this file is somewhat messy
"""

import os
import sys
from paver.easy import *
import paver.virtual
import paver.setuputils
from paver.setuputils import setup, find_package_data, find_packages

sphinxcontrib = False
try:
    from sphinxcontrib import paverutils
    sphinxcontrib = True
except ImportError:
    pass

sys.path.insert(0, '')

options = environment.options
# There is a bug in sqlalchemy 0.9.0, see gh#127
# There is a bug in beautifulsoup 4.2.0 that breaks imdb parsing, see http://flexget.com/ticket/2091
# There is a bug in requests 2.4.0 where it leaks urllib3 exceptions
# guessit 0.10.4 stops supporting python 2.6, the tests also start failing on 2.7
# Path keeps messing about with case, so anything under 6.2 will be broken now
install_requires = ['FeedParser>=5.1.3', 'SQLAlchemy >=0.7.5, !=0.9.0, <1.999', 'PyYAML',
                    'beautifulsoup4>=4.1, !=4.2.0, <4.4', 'html5lib>=0.11', 'PyRSS2Gen', 'pynzb', 'progressbar', 'rpyc',
                    'jinja2', 'requests>=1.0, !=2.4.0, <2.99', 'python-dateutil!=2.0, !=2.2', 'jsonschema>=2.0',
                    'python-tvrage', 'tmdb3', 'path.py>=6.2', 'guessit>=0.9.3, <0.10.4', 'apscheduler']
if sys.version_info < (2, 7):
    # argparse is part of the standard library in python 2.7+
    install_requires.append('argparse')

entry_points = {'console_scripts': ['flexget = flexget:main']}

# Provide an alternate exe on windows which does not cause a pop-up when scheduled
if sys.platform.startswith('win'):
    entry_points.setdefault('gui_scripts', []).append('flexget-headless = flexget:main')

with open("README.rst") as readme:
    long_description = readme.read()

# Populates __version__ without importing the package
__version__ = None
execfile('flexget/_version.py')
if not __version__:
    print 'Could not find __version__ from flexget/_version.py'
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
    package_data=find_package_data('flexget', package='flexget',
        exclude=['FlexGet.egg-info', '*.pyc'],
        only_in_packages=False),  # NOTE: the exclude does not seem to work
    zip_safe=False,
    test_suite='nose.collector',
    extras_require={
        'memusage': ['guppy'],
        'NZB': ['pynzb'],
        'TaskTray': ['pywin32'],
        'webui': ['flask>=0.7', 'cherrypy']
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

options(
    minilib=Bunch(
        # 'version' is included as workaround to https://github.com/paver/paver/issues/112, TODO: remove
        extra_files=['virtual', 'svn', 'version']
    ),
    virtualenv=Bunch(
        paver_command_line='develop'
    ),
    # sphinxcontrib.paverutils
    sphinx=Bunch(
        docroot='docs',
        builddir='build',
        builder='html',
        confdir='docs'
    ),
)


def set_init_version(ver):
    """Replaces the version with ``ver`` in _version.py"""
    import fileinput
    for line in fileinput.FileInput('flexget/_version.py', inplace=1):
        if line.startswith('__version__ = '):
            line = "__version__ = '%s'\n" % ver
        print line,


@task
def version():
    """Prints the version number of the source"""
    print __version__


@task
@cmdopts([('dev', None, 'Bumps to new development version instead of release version.')])
def increment_version(options):
    """Increments either release or dev version by 1"""
    print 'current version: %s' % __version__
    ver_split = __version__.split('.')
    dev = options.increment_version.get('dev')
    if 'dev' in ver_split[-1]:
        if dev:
            # If this is already a development version, increment the dev count by 1
            ver_split[-1] = 'dev%d' % (int(ver_split[-1].strip('dev') or 0) + 1)
        else:
            # Just strip off dev tag for next release version
            ver_split = ver_split[:-1]
    else:
        # Increment the revision number by one
        if len(ver_split) == 2:
            # We don't have a revision number, assume 0
            ver_split.append('1')
        else:
            ver_split[-1] = str(int(ver_split[-1]) + 1)
        if dev:
            ver_split.append('dev')
    new_version = '.'.join(ver_split)
    print 'new version: %s' % new_version
    set_init_version(new_version)


@task
@cmdopts([
    ('online', None, 'Run online tests')
])
def test(options):
    """Run FlexGet unit tests"""
    options.setdefault('test', Bunch())
    import nose
    from nose.plugins.manager import DefaultPluginManager

    cfg = nose.config.Config(plugins=DefaultPluginManager(), verbosity=2)

    args = []
    # Adding the -v flag makes the tests fail in python 2.7
    #args.append('-v')
    args.append('--processes=4')
    args.append('-x')
    if not options.test.get('online'):
        args.append('--attr=!online')
    args.append('--where=tests')

    # Store current path since --where changes it, restore when leaving
    cwd = os.getcwd()
    try:
        return nose.run(argv=args, config=cfg)
    finally:
        os.chdir(cwd)


@task
def clean():
    """Cleans up the virtualenv"""
    import os
    import glob

    for p in ('bin', 'Scripts', 'build', 'dist', 'include', 'lib', 'man',
              'share', 'FlexGet.egg-info', 'paver-minilib.zip', 'setup.py'):
        pth = path(p)
        if pth.isdir():
            pth.rmtree()
        elif pth.isfile():
            pth.remove()

    for pkg in set(options.setup.packages) | set(('tests',)):
        for filename in glob.glob(pkg.replace('.', os.sep) + "/*.py[oc~]"):
            path(filename).remove()


@task
@cmdopts([
    ('dist-dir=', 'd', 'directory to put final built distributions in'),
    ('revision=', 'r', 'minor revision number of this build')
])
def sdist(options):
    """Build tar.gz distribution package"""
    print 'sdist version: %s' % __version__
    # clean previous build
    print 'Cleaning build...'
    for p in ['build']:
        pth = path(p)
        if pth.isdir():
            pth.rmtree()
        elif pth.isfile():
            pth.remove()
        else:
            print 'Unable to remove %s' % pth

    # remove pre-compiled pycs from tests, I don't know why paver even tries to include them ...
    # seems to happen only with sdist though
    for pyc in path('tests/').files('*.pyc'):
        pyc.remove()

    for t in ['minilib', 'generate_setup', 'setuptools.command.sdist']:
        call_task(t)


@task
def coverage():
    """Make coverage.flexget.com"""
    # --with-coverage --cover-package=flexget --cover-html --cover-html-dir /var/www/flexget_coverage/
    import nose
    from nose.plugins.manager import DefaultPluginManager

    cfg = nose.config.Config(plugins=DefaultPluginManager(), verbosity=2)
    argv = ['bin/paver']
    argv.extend(['--attr=!online'])
    argv.append('--with-coverage')
    argv.append('--cover-html')
    argv.extend(['--cover-package', 'flexget'])
    argv.extend(['--cover-html-dir', '/var/www/flexget_coverage/'])
    nose.run(argv=argv, config=cfg)
    print 'Coverage generated'


@task
@cmdopts([
    ('docs-dir=', 'd', 'directory to put the documetation in')
])
def docs():
    if not sphinxcontrib:
        print 'ERROR: requires sphinxcontrib-paverutils'
        sys.exit(1)
    from paver import tasks
    if not os.path.exists('build'):
        os.mkdir('build')
    if not os.path.exists(os.path.join('build', 'sphinx')):
        os.mkdir(os.path.join('build', 'sphinx'))

    setup_section = tasks.environment.options.setdefault("sphinx", Bunch())
    setup_section.update(outdir=options.docs.get('docs_dir', 'build/sphinx'))
    call_task('html')


@task
@might_call('test', 'sdist')
@cmdopts([('no-tests', None, 'skips unit tests')])
def release(options):
    """Run tests then make an sdist if successful."""
    if not options.release.get('no_tests'):
        if not test():
            print 'Unit tests did not pass'
            sys.exit(1)

    print 'Making src release'
    sdist()


@task
def install_tools():
    """Install development / jenkins tools and dependencies"""

    try:
        import pip
    except ImportError:
        print 'FATAL: Unable to import pip, please install it and run this again!'
        sys.exit(1)

    try:
        import sphinxcontrib
        print 'sphinxcontrib INSTALLED'
    except ImportError:
        pip.main(['install', 'sphinxcontrib-paverutils'])

    pip.main(['install', '-r', 'jenkins-requirements.txt'])


@task
def clean_compiled():
    for root, dirs, files in os.walk('flexget'):
        for name in files:
            fqn = os.path.join(root, name)
            if fqn[-3:] == 'pyc' or fqn[-3:] == 'pyo' or fqn[-5:] == 'cover':
                print 'Deleting %s' % fqn
                os.remove(fqn)


@task
@consume_args
def pep8(args):
    try:
        import pep8
    except:
        print 'Run bin/paver install_tools'
        sys.exit(1)

    # Ignoring certain errors
    ignore = [
        'E711', 'E712',  # These are comparisons to singletons i.e. == False, and == None. We need these for sqlalchemy.
        'W291', 'W293', 'E261',
        'E128'  # E128 continuation line under-indented for visual indent
    ]
    styleguide = pep8.StyleGuide(show_source=True, ignore=ignore, repeat=1, max_line_length=120,
                                 parse_argv=args)
    styleguide.input_dir('flexget')
