from __future__ import unicode_literals, division, absolute_import
from flask import render_template, Blueprint
from flexget.ui import register_plugin, webui_app

home = Blueprint('home', __name__)


@webui_app.route('/')
@webui_app.route('/home')
def index():
    return render_template('home/home.html')

register_plugin(home, menu='Home', order=0)
