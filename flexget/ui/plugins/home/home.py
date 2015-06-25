from __future__ import unicode_literals, division, absolute_import
from flask import render_template
from flexget.ui import register_plugin, Blueprint, webui_app

home = Blueprint('home', __name__)
register_plugin(home)


@webui_app.route('/')
def index():
    return render_template('home/index.html')


home.register_angular_route(
    '',
    url=home.url_prefix,
    template_url='index.html',
)
