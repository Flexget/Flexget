from pathlib import Path

import yaml


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
    pass


class FGDumper(yaml.SafeDumper):
    # Set up the dumper to increase the indent for lists
    def increase_indent(self, flow=False, indentless=False):
        super().increase_indent(self, flow, False)


def _include(loader: FGLoader, node: yaml.nodes.Node):
    filename = Path(loader.name).parent / node.value
    with filename.open(encoding="utf-8") as f:
        return load(f)


def _include_named(loader: FGLoader, node: yaml.nodes.Node):
    directory = Path(loader.name).parent / node.value
    result = {}
    for file in directory.iterdir():
        if file.suffix not in ['.yaml', '.yml']:
            continue
        with file.open(encoding="utf-8") as f:
            result[file.name] = load(f)


FGLoader.add_constructor("!include", _include)
FGLoader.add_constructor("!include_named", _include_named)
