import logging
from flask import render_template, request, flash, redirect, Module, escape
from flexget.webui import register_plugin, manager

execute = Module(__name__, url_prefix='/execute')

log = logging.getLogger('ui.execute')


@execute.route('/', methods=['POST', 'GET'])
def index():
    if request.method == 'POST':
        options = manager.parser.parse_args(request.form.get('options', ''))[0]
        if manager.parser.error_msg:
            flash(escape(manager.parser.error_msg), 'error')
        else:
            flash('Manual execution started.', 'success')
            from flexget.webui import executor
            executor.execute(options)
    return render_template('execute.html')

register_plugin(execute, menu='Execute')
