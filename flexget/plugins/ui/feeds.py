from flexget.webui import app, render, manager


@app.route('/feeds')
def plugins():
    names = ['foo', 'bar']
    render('feeds.html', names)
