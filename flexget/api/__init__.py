from __future__ import unicode_literals, division, absolute_import

import pkgutil

from importlib import import_module

# Import API Sub Modules
for loader, module_name, is_pkg in pkgutil.walk_packages(__path__):
    import_module('.{}'.format(module_name), 'flexget.api')
