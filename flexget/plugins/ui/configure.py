from flexget.webui import manager, register_plugin
from flexget.feed import Feed
from flask import render_template, request, flash, redirect, Module
import yaml
import logging
from flask.helpers import url_for

configure = Module(__name__, url_prefix='/configure')

log = logging.getLogger('ui.configure')


class FGDumper(yaml.Dumper):

    def increase_indent(self, flow=False, indentless=False):
        return super(FGDumper, self).increase_indent(flow, False)


@configure.route('/')
def index():
    return render_template('configure.html')


@configure.route('/delete/<root>/<name>')
def delete(root, name):
    log.info('Deleting %s %s' % (root, name))
    return redirect(url_for('index'))


@configure.route('/edit/text/<root>/<name>', methods=['POST', 'GET'])
def edit_text(root, name):

    context = {
        'name': name,
        'root': root}

    if request.method == 'POST':
        context['config'] = request.form['config']
        try:
            config = yaml.load(request.form['config'])
        except yaml.scanner.ScannerError, e:
            flash('Invalid YAML document: %s' % e, 'error')
            log.exception(e)
        else:
            # valid yaml, not run validator
            errors = Feed.validate_config(config)
            if errors:
                for error in errors:
                    flash(error, 'error')
                context['config'] = request.form['config']
            else:
                flash('Configuration saved', 'info')
                context['config'] = yaml.dump(config, Dumper=FGDumper, default_flow_style=False)
    else:
        config = manager.config[root][name]
        context['config'] = yaml.dump(config, Dumper=FGDumper, default_flow_style=False)

    return render_template('configure_text.html', **context)

register_plugin(configure, menu='Configure', order=10)
