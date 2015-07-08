from __future__ import unicode_literals, division, absolute_import

from flexget.ui import register_plugin, register_js, Blueprint, register_menu, register_css

execute = Blueprint('execute', __name__)
register_plugin(execute)

execute.register_angular_route(
    '',
    url=execute.url_prefix,
    template_url='execute.html',
    controller='ExecuteCtrl'
)

execute.register_angular_route(
    'log',
    url='/log',
    template_url='log.html',
    controller='ExecuteLogCtrl',
)

execute.register_angular_route(
    'history',
    url='/history',
    template_url='history.html',
    controller='ExecuteHistoryCtrl',
)

register_js('execute', 'js/controllers.js', bp=execute)
register_js('angular-oboe', 'js/libs/angular-oboe.js', bp=execute)
register_js('oboe-browser', 'js/libs/oboe-browser.js', bp=execute)

register_css('execute', 'css/execute.css', bp=execute, order=99)

register_menu(execute.url_prefix, 'Execute', icon='fa fa-cog')
