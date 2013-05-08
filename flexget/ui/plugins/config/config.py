from __future__ import unicode_literals, division, absolute_import
import logging

from flask import request, Module, jsonify, json

from flexget.ui.webui import manager, register_plugin


config = Module(__name__)

log = logging.getLogger('ui.config')


@config.route('/', methods=['GET', 'POST'])
def root():
    if request.method == 'POST':
        manager.config = json.loads(request.data)
    return jsonify(manager.config)


def getset_item(obj, item, set=None):
    """
    Get `item` in either a dict or a list `obj`
    If `set` is specified, `item` in `obj` will be set to `set`s value
    """
    # We don't know whether path elements are strings or ints, so try both
    for func in [int, lambda x: x]:
        try:
            item = func(item)
            if set is not None:
                obj[item] = set
            return obj[item]
        except (TypeError, LookupError, ValueError):
            pass
    raise LookupError('%s not in config' % item)


@config.route('/<path:path>', methods=['GET', 'POST'])
def with_path(path):
    path = path.split('/')
    result = manager.config
    try:
        for elem in path[:-1]:
            result = getset_item(result, elem)
        elem = path[-1]
        if request.method == 'POST':
            getset_item(result, elem, set=json.loads(request.data))
        return jsonify(getset_item(result, elem))
    except LookupError as e:
        return unicode(e), 404


register_plugin(config)
