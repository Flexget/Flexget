from flexget.webui import register_plugin
from flask import render_template, Module

feeds = Module(__name__)


@feeds.route('/')
def index():
    names = ['foo', 'bar']
    return render_template('feeds.html')

register_plugin(feeds)
