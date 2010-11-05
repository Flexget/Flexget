from flexget.webui import app, register_menu
from flask import render_template


@app.route('/log')
def log():
    return render_template('log.html')


register_menu('/log', 'Log', order=256)
