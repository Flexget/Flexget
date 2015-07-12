from __future__ import unicode_literals, division, absolute_import

from flexget.ui import register_plugin, Blueprint, register_menu

log_viewer = Blueprint('log_viewer', __name__)
register_plugin(log_viewer)

log_viewer.register_angular_route(
    '',
    url=log_viewer.url_prefix,
    template_url='index.html',
    controller='LogViewCtrl'
)


log_viewer.register_css('log_viewer', 'css/log_viewer.css', order=99)
log_viewer.register_js('log_viewer', 'js/log_viewer.js')
log_viewer.register_js('angular-oboe', 'js/libs/angular-oboe.js')
log_viewer.register_js('oboe-browser', 'js/libs/oboe-browser.js')


register_menu(log_viewer.url_prefix, 'Log', icon='fa fa-file-text-o')
