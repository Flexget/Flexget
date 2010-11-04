from flexget.webui import app, render, manager, register_menu, menu_current


@app.route('/configure')
@menu_current('configure')
def plugins():
    return render('configure.html')
    
    
@app.route('/configure/<root>/<name>')
def configure(root, name):
    # TODO: plugins = manager.feeds ...
    plugins = ['hard coded', 'list']
    return render('configure.html')


register_menu('/configure', 'Configure', order=10)
