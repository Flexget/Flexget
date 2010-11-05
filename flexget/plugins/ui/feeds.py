from flexget.webui import app, manager


@app.route('/feeds')
def plugins():
    names = ['foo', 'bar']
    render('feeds.html', names)
