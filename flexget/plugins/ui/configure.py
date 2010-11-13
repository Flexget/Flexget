from flexget.webui import manager, register_plugin
from flexget.feed import Feed
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

    context = {
        'name': name,
        'root': root}

    if request.method == 'POST':
        # TODO: validate configuration
        config = yaml.load(request.form['config'])
        errors = Feed.validate_config(config)
        if not errors:
            # If no errors are returned from validator
            flash('Configuration saved')
            context['config'] = yaml.dump(config, Dumper=FGDumper, default_flow_style=False)
        else:
            flash('Invalid config')
            context['config'] = request.form['config']
            context['errors'] = errors
    else:
        context['config'] = yaml.dump(config, Dumper=FGDumper, default_flow_style=False)

    return render_template('configure_edit.html', **context)

register_plugin(configure, menu='Configure', order=10)
