from __future__ import unicode_literals, division, absolute_import
from flask import render_template, Module
from flexget.ui.webui import register_plugin

home = Module(__name__, url_prefix='/home')


@home.route('/')
def index():
    return render_template('home/home.html')

register_plugin(home, menu='Home', order=0, home=True)
