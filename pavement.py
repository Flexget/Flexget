from paver.easy import *
import paver.virtual
import paver.setuputils
from paver import svn
from paver.setuputils import setup, find_package_data, find_packages

options = environment.options
setup(
    name='FlexGet',
    version='1.0-svn',
    description='FlexGet is a program aimed to automate downloading or processing content (torrents, podcasts, etc.) from different sources like RSS-feeds, html-pages, various sites and more.',
    author='Marko Koivusalo',
    author_email='',
    url='http://flexget.com',
    install_requires=['FeedParser', 'SQLAlchemy>0.5', 'PyYAML', 'BeautifulSoup', 'html5lib>=0.11'],
    packages=['flexget', 'flexget.plugins', 'flexget.utils'],
    package_data=find_package_data('flexget', package='flexget',
                                   only_in_packages=False),
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
    )
)

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
