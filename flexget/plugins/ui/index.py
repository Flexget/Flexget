from flexget.webui import app, render, register_menu


@app.route('/')
def index():
    return render('index.html')


register_menu('/', 'Home')    