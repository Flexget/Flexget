from flexget.webui import register_plugin
from flask import render_template, Module

home = Module(__name__, url_prefix='/home')


@home.route('/')
def index():
    return render_template('home.html')

register_plugin(home, menu='Home', order=0, home=True)
