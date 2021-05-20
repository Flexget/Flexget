import sys
import os  # noqa
from pathlib import Path

from loguru import logger  # noqa

import yaml

logger = logger.bind(name='yaml_config')


def load(stream, filename=None):
    # We don't use yaml.load directly so that we can add the base filename so that relative !includes work.
    loader = FGLoader(stream)
    loader.name = filename or getattr(stream, 'name', '')
    try:
        return loader.get_single_data()
    finally:
        loader.dispose()


def dump(data, stream=None, **kwargs):
    yaml.dump(data, stream=stream, dumper=FGDumper, **kwargs)


class FGLoader(yaml.SafeLoader):
    _base = None

    def get_config_path(self):
        if not self._base:
            FGLoader._base = Path(self.name).parent

        return FGLoader._base


class FGDumper(yaml.SafeDumper):
    # Set up the dumper to increase the indent for lists
    def increase_indent(self, flow=False, indentless=False):
        super().increase_indent(self, flow, False)


def list_files(dirname):
    return_flist = []

    if os.path.isfile(dirname):
        return_flist = [dirname]
        return return_flist

    for file in os.listdir(dirname):
        if file[0] in ['.', '_']:
            # Disable file include with _ and ignore hidden files/folders
            continue

        fpath = os.path.join(dirname, file)

        if os.path.isdir(fpath):
            return_flist = return_flist + list_files(fpath)
        elif os.path.isfile(fpath):
            return_flist.append(Path(fpath))

    return return_flist


def _check_include(file) -> bool:
    if file.suffix not in ['.yaml', '.yml']:
        return False
    elif file.name[0] in ['.', '_']:
        # Disable file include with _
        return False

    return True


def _include(loader: FGLoader, node: yaml.nodes.Node):
    """ Include files and dir, if a dict or list merges """

    includes, top_include = _include_named(loader, node, True)

    result_type = None
    result = {}
    for _, config in includes.items():
        if result_type and result_type != type(config):
            logger.critical(
                'Can\'t merge {} with {} including {}', result_type, type(config), str(top_include)
            )
            sys.exit(1)

        if isinstance(config, dict):
            result.update(config)
        elif isinstance(config, list):
            config += result
        else:
            result = config

        if not result_type:
            result_type = type(config)

    return result


def _include_list(loader: FGLoader, node: yaml.nodes.Node):
    """ Allways returns a merged list """

    includes, _ = _include_named(loader, node, True)

    result = []
    for _, config in includes.items():
        if isinstance(config, dict):
            for prop, list_config in config.items():
                result.append({prop: list_config})
        elif isinstance(config, list):
            result += config
        else:
            result.append(config)

    return result


def _include_named(loader: FGLoader, node: yaml.nodes.Node, get_tuple=False):
    """ Returns a dict with the name of the file as property """

    root_path = loader.get_config_path()
    top_include = root_path / node.value
    includes = list_files(top_include)

    result = {}
    for file in includes:
        if not _check_include(file):
            continue

        with file.open(encoding="utf-8") as f:
            result[file.stem] = load(f)

    if get_tuple:
        return result, top_include
    else:
        return result


FGLoader.add_constructor("!include", _include)
FGLoader.add_constructor("!include_list", _include_list)
FGLoader.add_constructor("!include_named", _include_named)
