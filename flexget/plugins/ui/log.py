from flexget.webui import app, render, register_menu, register_home


@app.route('/log')
def log():
    return render('log.html')


register_menu('/log', 'Log', order=256)
