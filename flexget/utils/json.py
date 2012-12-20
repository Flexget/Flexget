"""
Helper module that can load whatever version of the json module is available.
Plugins can just import the methods from this module.
"""
from __future__ import unicode_literals, division, absolute_import
from flexget.plugin import DependencyError

try:
    import simplejson as json
except ImportError:
    try:
        import json
    except ImportError:
        try:
            # Google Appengine offers simplejson via django
            from django.utils import simplejson as json
        except ImportError:
            raise DependencyError(missing='simplejson')

load = json.load
loads = json.loads
dump = json.dump
dumps = json.dumps
