from paver.easy import *
import paver.virtual
import paver.setuputils
from paver import svn
from paver.setuputils import setup, find_package_data, find_packages

# TODO:
#  * pylint is not listed as dependency (task: pylint)
#    * the correct package to install is bin/easy_install logilab.pylintinstaller
#      this will however give tons of errors, and still work ..
#  * coverage is not listed as dependency (task: release_coverage)

PROJECT_DIR = path(__file__).dirname()

options = environment.options
setup(
    name='FlexGet',
    version='1.0-svn',
    description='FlexGet is a program aimed to automate downloading or processing content (torrents, podcasts, etc.) from different sources like RSS-feeds, html-pages, various sites and more.',
    author='Marko Koivusalo',
    author_email='',
    url='http://flexget.com',
    install_requires=['FeedParser', 'SQLAlchemy>0.5', 'PyYAML', 'BeautifulSoup', 'html5lib>=0.11', 'pygooglechart'],
    packages=['flexget', 'flexget.plugins', 'flexget.utils', 'flexget.utils.titles'],
    package_data=find_package_data('flexget', package='flexget', only_in_packages=False),
    zip_safe=False,
    test_suite='nose.collector',
    setup_requires=['nose>=0.11'],
    entry_points="""
        [console_scripts]
        flexget = flexget:main
    """
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
    pylint = Bunch(
        check_modules = ['flexget'],
        quiet = False,
        verbose = False,
        quiet_args = ['--reports=no', '--disable-checker=similarities'],
        pylint_args = ['--rcfile=pylint.rc', '--include-ids=y'],
        ignore = False
    )
    
)

def freplace(name, what_str, with_str):
    import fileinput
    for line in fileinput.FileInput(name, inplace=1):
        if what_str in line:
            line=line.replace(what_str, with_str)
        print line,

@task
@needs(['minilib', 'generate_setup', 'setuptools.command.sdist'])
def sdist():
    """Generates the tar.gz"""
    pass

@task
@cmdopts([
    ('online', None, 'Run online tests')
])
def test(options):
    """Run FlexGet unit tests"""
    import nose
    from nose.plugins.manager import DefaultPluginManager

    cfg = nose.config.Config(plugins=DefaultPluginManager(), verbosity=2)

    argv = ['bin/paver']

    if not hasattr(options, 'online'):
        argv.extend(['--attr=!online'])
        
    argv.append('-v')
    
    nose.run(argv=argv, config=cfg)

@task
def clean():
    """Cleans up the virtualenv"""
    for p in ('bin', 'build', 'dist', 'docs', 'include', 'lib', 'man',
            'share', 'FlexGet.egg-info', 'paver-minilib.zip', 'setup.py'):
        pth = path(p)
        if pth.isdir():
            pth.rmtree()
        elif pth.isfile():
            pth.remove()


@task
@needs(["minilib", "generate_setup", "setuptools.command.bdist_egg"])
def bdist_egg():
    pass

@task
def release_coverage():
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

@task
@consume_args
def release(args):
    """Make a FlexGet release. Same as bdist_egg but adds version information."""
    if len(args) != 1:
        print 'Version number must be specified, ie. paver release 1.0b9'
        return
    ver = args[0]
    
    # replace version number
    freplace('flexget/__init__.py', "__version__ = '{subversion}'", "__version__ = '%s'" % ver)

    # run unit tests
    test(environment.options) # dunno if param is correct ..

    # hack version number into setup( ... options='1.0-svn' ...)
    from paver import tasks
    setup_section = tasks.environment.options.setdefault("setup", Bunch())
    setup_section.update(version=ver)
    
    egg_options = ['-d', '/var/www/flexget_dist/unstable'] # hmph, how can I pass params to it? doesn't seem to work ..
    bdist_egg(egg_options)
    
    # hack since -d does not work ..
    import os
    import shutil
    dest = '/var/www/flexget_dist/unstable/'
    for name in os.listdir('dist'):
        if os.path.exists(os.path.join(dest, name)):
            print 'Skipped copying %s, destination already exists' % name
        shutil.move(os.path.join('dist', name), os.path.join(dest, name))

    # restore version ...
    freplace('flexget/__init__.py', "__version__ = '%s'" % ver, "__version__ = '{subversion}'")

@task
@cmdopts([
    ('pylint-command=', 'c', 'Specify a custom pylint executable'),
    ('quiet', 'q', 'Disables a lot of the pylint output'),
    ('verbose', 'v', 'Enables detailed output'),
    ('ignore', 'i', 'Ignore PyLint errors')
])
def pylint(options):
    
    import os.path
    if not os.path.exists('bin/pylint'):
        raise paver.tasks.BuildFailure('PyLint not installed!\n'+\
                                       'Run bin/easy_install logilab.pylintinstaller\n' + \
                                       'Do not be alarmed by the errors it may give, it still works ..')
        
    
    """Check the source code using PyLint."""
    from pylint import lint
    
    # Initial command.
    arguments = []
    
    if options.pylint.quiet:
        arguments.extend(options.pylint.quiet_args)
        
    if 'pylint_args' in options.pylint:
        arguments.extend(list(options.pylint.pylint_args))
    
    if not options.pylint.verbose:
        arguments.append('--errors-only')
    
    # Add the list of paths containing the modules to check using PyLint.
    arguments.extend(str(PROJECT_DIR / module) for module in options.check_modules)
    
    # By placing run_pylint into its own function, it allows us to do dry runs
    # without actually running PyLint.
    def run_pylint():
        # Add app folder to path.
        sys.path.insert(0, PROJECT_DIR)
        
        print 'Running pylint (this may take a while)'
        # Runs the PyLint command.
        try:
            lint.Run(arguments)
        # PyLint will `sys.exit()` when it has finished, so we need to catch
        # the exception and process it accordingly.
        except SystemExit, exc:
            return_code = exc.args[0]
            if return_code != 0 and (not options.pylint.ignore):
                raise paver.tasks.BuildFailure('PyLint finished with a non-zero exit code')
    
    return dry('bin/pylint ' + ' '.join(arguments), run_pylint)