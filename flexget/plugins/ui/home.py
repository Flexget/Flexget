from flexget.webui import app, render, register_menu, register_home


@app.route('/home')
def home():
    return render('home.html')


register_menu('/home', 'Home', order=0)
register_home('home')
