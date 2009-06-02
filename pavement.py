from paver.easy import *
import paver.virtual
import paver.setuputils
import re

from paver import svn

from paver.setuputils import setup, find_package_data, find_packages

options = environment.options
setup(
    name='flexget',
    version='0.9.4',
    description='FlexGet is a program aimed to automate downloading or processing content (torrents, podcasts, etc.) from different sources like RSS-feeds, html-pages, various sites and more.',
    author='',
    author_email='',
    url='http://flexget.com',
    install_requires=['SQLAlchemy>0.5', 'PyYAML', 'BeautifulSoup==3.0.7a'],
    packages=['flexget', 'flexget.plugins', 'flexget.utils'],
    package_data=find_package_data("flexget", package="flexget",
                                   only_in_packages=False),
    zip_safe=False,
    entry_points="""
        [console_scripts]
        flexget = flexget:main
    """
)
options(
    minilib=Bunch(
        extra_files=["virtual", "svn"]
    ),
    virtualenv=Bunch(
        paver_command_line="develop",
        unzip_setuptools=True
    )
)

@task
@needs(['minilib', 'generate_setup', 'setuptools.command.sdist'])
def sdist():
    """Generates the tar.gz"""
    pass

@task
@cmdopts([('online', None, 'Run online tests')])
def test(options):
    import test
    test.test_all(options)

@task
def clean():
    """Cleans up the virtualenv"""
    for p in ('bin', 'build', 'dist', 'docs', 'include', 'lib', 'man',
            'share', 'flexget.egg-info', 'paver-minilib.zip', 'setup.py'):
        pth = path(p)
        if pth.isdir():
            pth.rmtree()
        elif pth.isfile():
            pth.remove()

@task
@cmdopts([
    ('rev=', 'r', 'Build specific revision'),
    ('path=', 'p', 'SVN repository path'),
    ('zip=', 'z', 'Path for a zip'),
    ('tag=', 't', 'Tag package name, used instead of revision')
])
def build_release(options):
    export_path = path('build')
    if not export_path.exists():
        export_path.makedirs()

    export_path = export_path / 'flexget'

    if hasattr(options, 'zip'):
        if options.zip[-1:] == '/':
            options.zip = options.zip[:-1]
    else:
        options['zip'] = '/var/www/flexget_dist'

    if not hasattr(options, 'rev'):
        options['rev'] = ""

    if not hasattr(options, 'path'):
        options['path'] = 'http://svn.flexget.com/trunk'

    output = sh("svn export %s%s %s" % (svn._format_revision(options.rev), options.path, export_path), capture=True)
    m = re.search('Exported revision (\d+)', output)
    if not m:
        raise Exception('no rev found from svn export?')
    rev = m.groups()[0]

    path(export_path / 'quality_check.sh').remove()

    if not hasattr(options, 'tag'):
        package_name = path(options.zip) / (r"FlexGet_(%s).zip" % rev)
    else:
        package_name = path(options.zip) / ("FlexGet_%s.zip" % options.tag)

    sh("7z a -tzip \"%s\" %s" % (package_name, export_path))

    export_path.rmtree()

    print package_name

    if not package_name.exists():
        print '!! FAILED to create %s' % package_name
    else:
        print 'Created: %s' % package_name
