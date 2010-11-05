from flexget.webui import app, manager, register_menu
from flask import render_template


@app.route('/configure')
def plugins():
    return render_template('configure.html')


@app.route('/configure/<root>/<name>')
def configure(root, name):
    # TODO: plugins = manager.feeds ...
    plugins = ['hard coded', 'list']
    return render_template('configure.html')


register_menu('/configure', 'Configure', order=10)
