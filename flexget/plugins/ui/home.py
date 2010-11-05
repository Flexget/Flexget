from flexget.webui import app, register_menu, register_home
from flask import render_template


@app.route('/home')
def home():
    return render_template('home.html')


register_menu('/home', 'Home', order=0)
register_home('home')
