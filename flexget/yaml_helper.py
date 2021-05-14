from collections import OrderedDict

from ruamel.yaml import YAML, YAMLError
from ruamel.yaml.constructor import RoundTripConstructor

yaml = YAML(typ="safe")


class ExtRoundTripConsturctor(RoundTripConstructor):
    """Extended SafeConstructor."""

    def construct_object(self, node, deep=False):  # type: (Any, bool) -> Any
        result = super().construct_object(node, deep=deep)
        try:
            result.filename = node.start_mark.name
        except:
            pass
        return result


def load_yaml(file_name: str):
    yaml = YAML(typ="rt")
    yaml.Constructor = ExtRoundTripConsturctor

    try:
        with open(file_name, encoding="utf-8") as conf_file:
            # If configuration file is empty YAML returns None
            # We convert that to an empty dict
            return yaml.load(conf_file) or OrderedDict()
    except YAMLError as exc:
        # logger.error("YAML error in %s: %s", file_name, exc)
        raise
    except UnicodeDecodeError as exc:
        # logger.error("Unable to read file %s: %s", file_name, exc)
        raise
