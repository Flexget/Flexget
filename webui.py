#!/usr/bin/python
# -*- coding: utf-8 -*-

import time
import string
import textwrap

import web
from manager import Manager

urls = (
      '/', 'index',
      '/modules', 'modules',
      '/run', 'run',
      )

render = web.template.render('templates/', cache=False)

manager = Manager()
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
            if modules.index(module) > 0:
                event = ""
            else:
                event = module['event']

            if not module['instance'].__doc__:
                module['doc'] = ""
            else:
                module['doc'] = textwrap.dedent(module['instance'].__doc__)
                
        print render.modules(roles, modules);

class run:
    def GET(self):
        start = time.time()
        manager.execute()
        end = time.time()
        duration = end-start
        print duration

class index:
    def GET(self):
        enabled = []
        for source in filter(lambda x: not x.startswith("_"), manager.config.get('feeds', {}).keys()):
            enabled.append(source)

        disabled = []
        for source in filter(lambda x: x.startswith("_"), manager.config.get('feeds', {}).keys()):
            disabled.append(source[1:])

        print render.index(enabled, disabled)

web.webapi.internalerror = web.debugerror

if __name__ == "__main__":
    print "FlexGet Web UI starting..."
    web.run(urls, globals(), web.reloader)

