from __future__ import unicode_literals, division, absolute_import

from flexget.ui import register_plugin, register_js, Blueprint, register_menu

execute = Blueprint('execute', __name__)
register_plugin(execute)

execute.register_angular_route(
    '',
    url=execute.url_prefix,
    template_url='execute.html',
    controller='ExecuteCtrl'
)

execute.register_angular_route(
    'history',
    url='/history',
    template_url='history.html',
    controller='ExecuteHistoryCtrl',
)

register_js('execute', 'js/execute.js', bp=execute)

register_menu(execute.url_prefix, 'Execute', icon='fa fa-cog')
