from __future__ import unicode_literals, division, absolute_import

from flexget.ui import register_plugin, register_js, Blueprint

authentication = Blueprint('authentication', __name__)
register_plugin(authentication)

register_js('authentication', 'js/authentication.js', bp=authentication)
register_js('http-auth-interceptor', 'js/http-auth-interceptor.js', bp=authentication)
