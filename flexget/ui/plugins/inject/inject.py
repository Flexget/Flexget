from __future__ import unicode_literals, division, absolute_import
import logging
import posixpath
import urlparse
from flask import render_template, request, flash, redirect, Module
from flask.helpers import url_for
from flexget.ui.webui import register_plugin, executor
from flexget.entry import Entry

inject = Module(__name__, url_prefix='/inject')

log = logging.getLogger('ui.inject')


@inject.route('/')
def index():
    return render_template('inject/inject.html')


@inject.route('/do', methods=['POST', 'GET'])
def do_inject():
    fields = {}
    # Requests is a special dict, and cannot be passed as keyword arguments, make it into a normal dict.
    for key, value in request.values.iteritems():
        # Translate on and off to True and False
        if value == 'on':
            fields[key] = True
        elif value == 'off':
            fields[key] = False
        else:
            fields[key] = value
    # If we only got a url, make a title from the url filename
    fields['title'] = fields.get('title') or posixpath.basename(urlparse.urlsplit(fields.get('url', '')).path)

    if fields.get('title') and fields.get('url'):
        # Create the entry for injection
        entry = Entry(**fields)
        executor.execute(options={'dump_entries': True}, entries=[entry])
        flash('Scheduled execution for entry `%s`' % entry['title'], 'success')
    else:
        flash('Title and URL required for inject.', 'error')

    return redirect(url_for('index'))


register_plugin(inject)
