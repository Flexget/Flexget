from flexget.webui import app, manager, register_menu
from flask import render_template, request, flash
import yaml


@app.route('/configure')
def configure():
    return render_template('configure.html')


@app.route('/configure/<root>/<name>', methods=['POST', 'GET'])
def edit(root, name):
    config = manager.feeds[name].config

    if request.method == 'POST':
        # TODO: validate configuration
        flash('Configuration saved')
        config = yaml.load(request.form['config'])

    context = {
        'name': name,
        'root': root,
        'config': yaml.dump(config, default_flow_style=False)}

    return render_template('configure_edit.html', **context)


register_menu('/configure', 'Configure', order=10)
