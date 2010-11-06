from flexget.webui import manager, register_plugin
from flask import render_template, request, flash, Module
import yaml

configure = Module(__name__, url_prefix='/configure')


class FGDumper(yaml.Dumper):

    def increase_indent(self, flow=False, indentless=False):
        return super(FGDumper, self).increase_indent(flow, False)


@configure.route('/')
def index():
    return render_template('configure.html')


@configure.route('/<root>/<name>', methods=['POST', 'GET'])
def edit(root, name):
    config = manager.config[root][name]

    if request.method == 'POST':
        # TODO: validate configuration
        flash('Configuration saved')
        config = yaml.load(request.form['config'])

    context = {
        'name': name,
        'root': root,
        'config': yaml.dump(config, Dumper=FGDumper, default_flow_style=False)}

    return render_template('configure_edit.html', **context)

register_plugin(configure, menu='Configure', order=10)
