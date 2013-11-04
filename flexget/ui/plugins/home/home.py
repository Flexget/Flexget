from __future__ import unicode_literals, division, absolute_import
from flask import render_template, Blueprint
from flexget.ui.webui import register_plugin

home = Blueprint('home', __name__)


@home.route('/')
def index():
    return render_template('home/home.html')

register_plugin(home, menu='Home', order=0, home=True)
