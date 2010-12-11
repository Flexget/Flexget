import logging
from flask import render_template, request, Response, redirect, flash
from flask import Module, escape
from flexget.webui import register_plugin, manager

execute = Module(__name__, url_prefix='/execute')

log = logging.getLogger('ui.execute')


@execute.route('/', methods=['POST', 'GET'])
def index():
    context = {'help': manager.parser.get_help()}
    if request.method == 'POST':
        options = manager.parser.parse_args(request.form.get('options', ''))[0]
        if manager.parser.error_msg:
            flash(escape(manager.parser.error_msg), 'error')
            context['options'] = request.form['options']
        else:
            flash('Manual execution started.', 'success')
            from flexget.webui import executor
            executor.execute(options)
            context['execute_progress'] = progress(return_list=True)
        
    return render_template('execute.html', **context)


@execute.route('/progress.json')
def progress(return_list=False):
    '''
    Gives takes messages from the queue and exports them to JSON.
    '''
    context = {'progress':    
        ["Did something on a file.", # < v Fill me in order.
        "Downloading Inception.2.Thought Police.(2012).axxo.avi",
        "Rejected something becasue you've downloaded it already. (yeah right, eheh)"]}
        
    if return_list:
        return context['progress']
        
    json_rendered = render_template('execute_progress.json', **context)
    return Response(json_rendered, mimetype='application/json')


register_plugin(execute, menu='Execute')
