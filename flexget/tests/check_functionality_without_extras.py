import importlib
import pkgutil

import flexget
from flexget.plugin import DependencyError

for _, module_name, _ in pkgutil.walk_packages(
    path=flexget.__path__, prefix=f'{flexget.__name__}.'
):
    try:
        importlib.import_module(module_name)
    except DependencyError:
        pass
