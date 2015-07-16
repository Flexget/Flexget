from __future__ import unicode_literals, division, absolute_import

from flexget.ui import register_plugin, Blueprint, register_menu

log = Blueprint('log', __name__)
register_plugin(log)

log.register_angular_route(
    '',
    url=log.url_prefix,
    template_url='index.html',
    controller='LogViewCtrl'
)


log.register_css('log', 'css/log.css', order=99)
log.register_js('log', 'js/log.js')
log.register_js('angular-oboe', 'js/libs/angular-oboe.js')
log.register_js('oboe-browser', 'js/libs/oboe-browser.js')


register_menu(log.url_prefix, 'Log', icon='fa fa-file-text-o')
