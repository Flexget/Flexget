#!/usr/bin/python
# -*- coding: utf-8 -*-

import time

import web
from manager import Manager

urls = (
      '/', 'index',
      '/modules', 'modules',
      '/run', 'run',
      )

render = web.template.render('templates/', cache=False)

m = Manager()
m.initialize()

class modules:
    def GET(self):
        m.print_module_list()

class run:
    def GET(self):
        print "running"
        start = time.time()
        m.execute()
        end = time.time()
        duration = end-start
        print duration

class index:
    def GET(self):
        enabled = []
        for source in filter(lambda x: not x.startswith("_"), m.config.get('feeds', {}).keys()):
            enabled.append(source)

        disabled = []
        for source in filter(lambda x: x.startswith("_"), m.config.get('feeds', {}).keys()):
            disabled.append(source[1:])

        print render.index(enabled, disabled)

web.webapi.internalerror = web.debugerror

if __name__ == "__main__": web.run(urls, globals(), web.reloader)

