from flexget.webui import app, render, register_menu


@app.route('/schedule')
def scheduler():
    return render('schedule.html')


register_menu('/schedule', 'Schedule')
