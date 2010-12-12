from flexget.webui import manager, register_plugin
from flexget.feed import Feed
from flask import render_template, request, flash, redirect, Module
import yaml
import logging
from flask.helpers import url_for

configure = Module(__name__, url_prefix='/configure')

log = logging.getLogger('ui.configure')


@configure.route('/')
def index():
    return render_template('configure.html')


@configure.route('/new/<root>', methods=['POST', 'GET'])
def new_text(root):
    if root not in ['feeds', 'presets']:
        flash('Invalid root.', 'error')
        return redirect(url_for('index'))
    config_type = root.rstrip('s')
    context = {'root': root,
               'config': ''}
    if request.method == 'POST':
        name = request.form.get('name')
        if not name:
            flash('Enter a name for this %s' % config_type, 'error')
            context['config'] = request.form.get('config')
        else:
            # forward to edit_text
            pass

    return render_template('configure_text.html', **context)


@configure.route('/delete/<root>/<name>')
def delete(root, name):
    if root in manager.config and name in manager.config[root]:
        log.info('Deleting %s %s' % (root, name))
        del manager.config[root][name]
        manager.save_config()
        flash('Deleted %s.' % name, 'delete')
    return redirect(url_for('index'))


@configure.route('/edit/text/<root>/<name>', methods=['POST', 'GET'])
def edit_text(root, name):
    from flexget.manager import FGDumper
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
                manager.config[root][name] = config
                manager.save_config()
                flash('Configuration saved', 'info')
                context['config'] = yaml.dump(config, Dumper=FGDumper, default_flow_style=False)
    else:
        config = manager.config[root][name]
        context['config'] = yaml.dump(config, Dumper=FGDumper, default_flow_style=False)

    return render_template('configure_text.html', **context)

register_plugin(configure, menu='Configure', order=10)
