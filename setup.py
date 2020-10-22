import sys
from pathlib import Path
from typing import List

from setuptools import find_packages, setup

long_description = Path('README.rst').read_text()

# Populates __version__ without importing the package
__version__ = None
with open('flexget/_version.py', encoding='utf-8') as ver_file:
    exec(ver_file.read())  # pylint: disable=W0122
if not __version__:
    print('Could not find __version__ from flexget/_version.py')
    sys.exit(1)


def load_requirements(filename: str) -> List[str]:
    return [
        line.strip()
        for line in Path(filename).read_text().splitlines()
        if not line.startswith('#')
    ]


setup(
    name='FlexGet',
    version=__version__,
    description='FlexGet is a program aimed to automate downloading or processing content (torrents, podcasts, etc.) '
    'from different sources like RSS-feeds, html-pages, various sites and more.',
    long_description=long_description,
    long_description_content_type='text/x-rst',
    author='Marko Koivusalo',
    author_email='marko.koivusalo@gmail.com',
    license='MIT',
    url='https://flexget.com',
    project_urls={
        'Repository': 'https://github.com/Flexget/Flexget',
        'Issue Tracker': 'https://github.com/Flexget/Flexget/issues',
        'Forum': 'https://discuss.flexget.com',
    },
    packages=find_packages(exclude=['flexget.tests']),
    include_package_data=True,
    zip_safe=False,
    install_requires=load_requirements('requirements.txt'),
    tests_require=['pytest'],
    extras_require={'dev': load_requirements('dev-requirements.txt')},
    entry_points={
        'console_scripts': ['flexget = flexget:main'],
        'gui_scripts': [
            'flexget-headless = flexget:main'
        ],  # This is useful on Windows to avoid a cmd popup
    },
    python_requires='>=3.6',
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: Implementation :: CPython",
        "Programming Language :: Python :: Implementation :: PyPy",
    ],
)
