from flexget.webui import app, render, register_menu, menu_current


@app.route('/')
@menu_current('home')
def index():
    return render('index.html')


register_menu('/', 'Home', order=0)
