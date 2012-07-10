import os
import re
from paver.easy import *
import paver.virtual
import paver.setuputils
from paver import svn
from paver.setuputils import setup, find_package_data, find_packages

sphinxcontrib = False
try:
    from sphinxcontrib import paverutils
    sphinxcontrib = True
except ImportError:
    pass

sys.path.insert(0, '')

options = environment.options
install_requires = ['FeedParser>=5.1.2', 'SQLAlchemy >=0.7, <0.8', 'PyYAML', 'BeautifulSoup>=3.2, <3.3',
                    'html5lib>=0.11', 'PyRSS2Gen', 'pynzb', 'progressbar', 'jinja2', 'flask', 'cherrypy']
if sys.version_info < (2, 6):
    install_requires.append('requests==0.10.0')
    install_requires.append('python-dateutil<2.0') # dateutil 2.0 is python 3 only
else:
    install_requires.append('requests>=0.10, !=0.10.1, <0.11') #URL quoting bug in 0.10.1
    install_requires.append('python-dateutil!=2.0') # dateutil 2.1 started supporting python 2.6+ again
if sys.version_info < (2,7):
    # argparse is part of the standard library in python 2.7+
    install_requires.append('argparse')

entry_points = {
    'console_scripts': ['flexget = flexget:main'],
    'gui_scripts': ['flexget-webui = flexget.ui:main']}

# Provide an alternate exe on windows which does not cause a pop-up when scheduled
if sys.platform.startswith('win'):
    entry_points['gui_scripts'].append('flexget-headless = flexget:main')

setup(
    name='FlexGet',
    version='1.0', # our tasks append the r1234 (current svn revision) to the version number
    description='FlexGet is a program aimed to automate downloading or processing content (torrents, podcasts, etc.) from different sources like RSS-feeds, html-pages, various sites and more.',
    author='Marko Koivusalo',
    author_email='marko.koivusalo@gmail.com',
    license='MIT',
    url='http://flexget.com',
    install_requires=install_requires,
    packages=find_packages(exclude=['tests']),
    package_data=find_package_data('flexget', package='flexget',
                                   exclude=['FlexGet.egg-info', '*.pyc'],
                                   only_in_packages=False), # NOTE: the exclude does not seem to work
    zip_safe=False,
    test_suite='nose.collector',
    setup_requires=['nose>=0.11'],
    extras_require={
        'memusage':     ['guppy'],
        'NZB':          ['pynzb'],
        'TaskTray':     ['pywin32'],
    },
    entry_points=entry_points
)

options(
    minilib=Bunch(
        extra_files=['virtual', 'svn']
    ),
    virtualenv=Bunch(
        packages_to_install=['nose>=0.11'],
        paver_command_line='develop',
        unzip_setuptools=True
    ),
    # sphinxcontrib.paverutils
    sphinx=Bunch(
        docroot='docs',
        builddir='build',
        builder='html',
        confdir='docs'
    ),
)

def freplace(name, what_str, with_str):
    """Replaces a :what_str: with :with_str: in file :name:"""
    import fileinput
    for line in fileinput.FileInput(name, inplace=1):
        if what_str in line:
            line = line.replace(what_str, with_str)
        print line,

def set_init_version(ver):
    """Replaces the version with :ver: in __init__.py"""
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
    import os, glob

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
    ('dist-dir=', 'd', 'directory to put final built distributions in')
])
def sdist(options):
    """Build tar.gz distribution package"""

    revision = svn.info().get('last_changed_rev')

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

    ver = '%sr%s' % (options['version'], revision)

    print 'Building %s' % ver

    # hack for getting options from release task
    if hasattr(options, 'release'):
        if options.release.get('dist_dir'):
            options.setdefault('sdist', Bunch())['dist_dir'] = options.release.dist_dir
    else:
        if options.sdist.get('dist_dir'):
            options.setdefault('sdist', Bunch())['dist_dir'] = options.sdist.dist_dir

    # replace version number
    set_init_version(ver)

    # hack version number into setup( ... options='1.0' ...)
    from paver import tasks
    setup_section = tasks.environment.options.setdefault("setup", Bunch())
    setup_section.update(version=ver)

    for t in ['minilib', 'generate_setup', 'setuptools.command.sdist']:
        call_task(t)

    # restore version ...
    set_init_version('{subversion}')


@task
@cmdopts([
    ('dist-dir=', 'd', 'directory to put final built distributions in')
])
def make_egg(options):
    # naming this task to bdist_egg will make egg installation fail
    options.setdefault('release', Bunch())

    revision = svn.info().get('last_changed_rev')
    ver = '%sr%s' % (options['version'], revision)

    # hack version number into setup( ... options='1.0-svn' ...)
    from paver import tasks
    setup_section = tasks.environment.options.setdefault("setup", Bunch())
    setup_section.update(version=ver)

    # replace version number
    set_init_version(ver)

    print 'Making egg release'
    import shutil
    shutil.copytree('FlexGet.egg-info', 'FlexGet.egg-info-backup')

    if options.release.get('dist_dir'):
        options.setdefault('bdist_egg', Bunch())['dist_dir'] = options.release.dist_dir

    # hack for getting options from release task
    if hasattr(options, 'release'):
        if options.release.get('dist_dir'):
            options.setdefault('bdist_egg', Bunch())['dist_dir'] = options.release.dist_dir
    else:
        if options.sdist.get('dist_dir'):
            options.setdefault('bdist_egg', Bunch())['dist_dir'] = options.sdist.dist_dir

    for t in ["minilib", "generate_setup", "setuptools.command.bdist_egg"]:
        call_task(t)

    # restore version ...
    set_init_version('{subversion}')

    # restore egg info from backup
    print 'Removing FlexGet.egg-info ...'
    shutil.rmtree('FlexGet.egg-info')
    print 'Restoring FlexGet.egg-info'
    shutil.move('FlexGet.egg-info-backup', 'FlexGet.egg-info')


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
    setup_section = tasks.environment.options.setdefault("sphinx", Bunch())
    setup_section.update(outdir=options.docs.get('docs_dir', 'build/sphinx'))
    call_task('html')


@task
@cmdopts([
    ('online', None, 'runs online unit tests'),
    ('dist-dir=', 'd', 'directory to put final built distributions in'),
    ('no-tests', None, 'skips unit tests'),
    ('type=', None, 'type of release (src | egg)')
])
def release(options):
    """Make a FlexGet release. Same as bdist_egg but adds version information."""

    if options.release.get('type') not in ['src', 'egg']:
        print 'Invalid --type, must be src or egg'
        return

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
    if options.release.get('online'):
        options.setdefault('test', Bunch())['online'] = True
    if not options.release.get('no_tests'):
        if not test():
            print 'Unit tests did not pass'
            import sys
            sys.exit(1)

    if options.release.get('type') == 'egg':
        print 'Making egg release'
        make_egg(options)
    else:
        print 'Making src release'
        sdist(options)


@task
def install_tools():
    """Install development / hudson tools and dependencies"""

    try:
        import pip
    except:
        print 'FATAL: Unable to import pip, please install it and run this again!'
        return

    try:
        import sphinxcontrib
        print 'sphinxcontrib INSTALLED'
    except:
        pip.main(['install', 'sphinxcontrib-paverutils'])

    try:
        import pylint
        print 'Pylint INSTALLED'
    except:
        pip.main(['install', 'pylint']) # OR instead of pylint logilab.pylintinstaller ?

    try:
        import coverage
        print 'Coverage INSTALLED'
    except:
        pip.main(['install', 'coverage'])

    try:
        import nosexcover
        print 'Nose-xcover INSTALLED'
    except:
        pip.main(['install', 'http://github.com/cmheisel/nose-xcover/zipball/master'])

    try:
        import pep8
        print 'pep8 INSTALLED'
    except:
        pip.main(['install', 'pep8'])


@task
def clean_compiled():
    for root, dirs, files in os.walk('flexget'):
        for name in files:
            fqn = os.path.join(root, name)
            if fqn[-3:] == 'pyc' or fqn[-3:] == 'pyo' or fqn[-5:] == 'cover':
                print 'Deleting %s' % fqn
                os.remove(fqn)


@task
def pep8():
    try:
        import pep8
    except:
        print 'Run bin/paver install_tools'
        return
    pep8.options, pep8.args = pep8.process_options(['--show-source', '--ignore', 'E501,W291,W293,W601,E261', ''])
    pep8.options.repeat = 1

    for root, dirs, files in os.walk('flexget'):
        for name in files:
            if name[-2:] == 'py':
                fn = os.path.join(root, name)
                checker = pep8.Checker(fn)
                checker.check_all()

