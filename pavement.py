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
install_requires = ['FeedParser>=5.1.3', 'SQLAlchemy >=0.7.5, !=0.9.0, <0.9.99', 'PyYAML',
                    # There is a bug in beautifulsoup 4.2.0 that breaks imdb parsing, see http://flexget.com/ticket/2091
                    'beautifulsoup4>=4.1, !=4.2.0, <4.4', 'html5lib>=0.11', 'PyRSS2Gen', 'pynzb', 'progressbar', 'rpyc',
                    'jinja2', 'requests>=1.0, <2.99', 'python-dateutil!=2.0, !=2.2', 'jsonschema>=2.0', 'python-tvrage',
                    'tmdb3']
if sys.version_info < (2, 7):
    # argparse is part of the standard library in python 2.7+
    install_requires.append('argparse')

entry_points = {'console_scripts': ['flexget = flexget:main']}

# Provide an alternate exe on windows which does not cause a pop-up when scheduled
if sys.platform.startswith('win'):
    entry_points.setdefault('gui_scripts', []).append('flexget-headless = flexget:main')

with open("README.rst") as readme:
    long_description = readme.read()

setup(
    name='FlexGet',
    version='1.2',  # our tasks append the .1234 (current build number) to the version number
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
    """Replaces the version with ``ver`` in __init__.py"""
    import fileinput
    for line in fileinput.FileInput('flexget/__init__.py', inplace=1):
        if line.startswith('__version__ = '):
            line = "__version__ = '%s'\n" % ver
        print line,


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
], share_with=['make_egg'])
def sdist(options):
    """Build tar.gz distribution package"""

    if not options.sdist.get('revision'):
        print 'Revision number required.'
        sys.exit(1)
    revision = options.sdist.pop('revision')

    print 'Revision: %s' % revision

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

    ver = '%s.%s' % (options['version'], revision)

    print 'Building %s' % ver

    # replace version number
    set_init_version(ver)

    # hack version number into setup( ... options='1.0' ...)
    from paver import tasks
    setup_section = tasks.environment.options.setdefault("setup", Bunch())
    setup_section.update(version=ver)

    for t in ['minilib', 'generate_setup', 'setuptools.command.sdist']:
        call_task(t)

    # restore version ...
    set_init_version('{git}')
    return ver


@task
@cmdopts([
    ('dist-dir=', 'd', 'directory to put final built distributions in'),
    ('revision=', 'r', 'minor revision number of this build')
], share_with=['sdist'])
def make_egg(options):
    # naming this task to bdist_egg will make egg installation fail

    if not options.make_egg.get('revision'):
        print 'Revision number required.'
        sys.exit(1)
    revision = options.make_egg.revision
    ver = '%s.%s' % (options['version'], revision)

    # hack version number into setup( ... options='1.0-svn' ...)
    from paver import tasks
    setup_section = tasks.environment.options.setdefault("setup", Bunch())
    setup_section.update(version=ver)

    # replace version number
    set_init_version(ver)

    print 'Making egg release'
    import shutil
    shutil.copytree('FlexGet.egg-info', 'FlexGet.egg-info-backup')

    options.setdefault('bdist_egg', Bunch())['dist_dir'] = options.make_egg.get('dist_dir')

    for t in ["minilib", "generate_setup", "setuptools.command.bdist_egg"]:
        call_task(t)

    # restore version ...
    set_init_version('{git}')

    # restore egg info from backup
    print 'Removing FlexGet.egg-info ...'
    shutil.rmtree('FlexGet.egg-info')
    print 'Restoring FlexGet.egg-info'
    shutil.move('FlexGet.egg-info-backup', 'FlexGet.egg-info')
    return ver


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
@might_call('test', 'sdist', 'make_egg')
@cmdopts([
    ('no-tests', None, 'skips unit tests'),
    ('type=', None, 'type of release (src | egg)'),
    ('ver-file=', None, 'java properties file to create with version number FG_VERSION')
])
def release(options):
    """Make a FlexGet release. Same as bdist_egg but adds version information."""

    if options.release.get('type') not in ['src', 'egg']:
        print 'Invalid --type, must be src or egg'
        sys.exit(1)

    print 'Cleaning build...'
    for p in ['build']:
        pth = path(p)
        if pth.isdir():
            pth.rmtree()
        elif pth.isfile():
            pth.remove()
        else:
            print 'Unable to remove %s' % pth

    # run unit tests
    if not options.release.get('no_tests'):
        if not test():
            print 'Unit tests did not pass'
            sys.exit(1)

    if options.release.get('type') == 'egg':
        print 'Making egg release'
        ver = make_egg()
    else:
        print 'Making src release'
        ver = sdist()

    if getattr(options.release, 'ver_file', False):
        with open(options.release.ver_file, 'w') as ver_file:
            ver_file.write('FG_VERSION=%s' % ver)

@task
def install_tools():
    """Install development / jenkins tools and dependencies"""

    try:
        import pip
    except:
        print 'FATAL: Unable to import pip, please install it and run this again!'
        sys.exit(1)

    try:
        import sphinxcontrib
        print 'sphinxcontrib INSTALLED'
    except:
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
