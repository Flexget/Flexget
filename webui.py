#!/usr/bin/python
# -*- coding: utf-8 -*-

import time
import string

import web
from manager import Manager

urls = (
      '/', 'index',
      '/modules', 'modules',
      '/run', 'run',
      )

render = web.template.render('templates/', cache=False)

m = Manager()
manager = m
manager.initialize()

class modules:
    def GET(self):
        modules = []
        roles = {}
        for event in manager.EVENTS:
            ml = manager.get_modules_by_event(event)
            for m in ml:
                dupe = False
                for module in modules:
                    if module['keyword'] == m['keyword']: dupe = True
                if not dupe:
                    modules.append(m)
            # build roles list
            for m in ml:
                if roles.has_key(m['keyword']):
                    roles[m['keyword']].append(event)
                else:
                    roles[m['keyword']] = [event]
        for module in modules:
            # do not include test classes, unless in debug mode
            if module.get('debug_module', False):
                continue
            event = module['event']
            if modules.index(module) > 0: event = ""
            doc = "Yes"
            if not module['instance'].__doc__:
                doc = "No"
            #print "%-20s%-30s%s" % (module['keyword'], string.join(roles[module['keyword']], ', '), doc)

        print render.modules(roles, modules);

class run:
    def GET(self):
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

if __name__ == "__main__":
    print "FlexGet Web UI starting..."
    web.run(urls, globals(), web.reloader)

