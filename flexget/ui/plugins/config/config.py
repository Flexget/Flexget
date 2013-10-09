from __future__ import unicode_literals, division, absolute_import
import logging

from flask import request, Blueprint, jsonify, json

from flexget.ui.webui import manager, register_plugin


config = Blueprint('config', __name__)

log = logging.getLogger('ui.config')


@config.route('/', methods=['GET', 'POST'])
def root():
    if request.method == 'POST':
        manager.config = json.loads(request.data)
    result = jsonify(manager.config)
    # TODO: This should not be hard coded
    result.headers[b'Content-Type'] += '; profile=/schema/root'
    return result


def getset_item(obj, item, set=None):
    """
    Get `item` in either a dict or a list `obj`
    If `set` is specified, `item` in `obj` will be set to `set`s value
    """
    # We don't know whether path elements are strings or ints, so try both
    for func in [lambda x: x, int]:
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
        result = jsonify(getset_item(result, elem))
    except LookupError as e:
        return unicode(e), 404
    # TODO: This should not be hard coded
    if len(path) == 2 and path[0] in ['tasks', 'presets']:
        result.headers[b'Content-Type'] += '; profile=/schema/plugins?context=task'
    return result


register_plugin(config)
