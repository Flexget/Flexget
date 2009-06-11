#!/usr/bin/python

from flexget.options import OptionParser
from flexget.manager import Manager
from flexget import plugin
import os
import os.path
import sys

def main():
    parser = OptionParser()
    plugin.load_plugins(parser)
    options = parser.parse_args()[0]

    if os.path.exists(os.path.join(sys.path[0], '..', 'pavement.py')):
        basedir = os.path.dirname(os.path.abspath(sys.path[0]))
    else:
        basedir = sys.path[0]

    if os.path.exists(os.path.join(basedir, 'config.yml')):
        config_base = basedir
    else:
        config_base = os.path.join(os.path.expanduser('~'), '.flexget')

    manager = Manager(options, config_base)

    lockfile = os.path.join(config_base, ".%s-lock" % manager.configname)

    if os.path.exists(lockfile):
        f = file(lockfile)
        pid = f.read()
        f.close()
        print "Another process (%s) is running, will exit." % pid.strip()
        print "If you're sure there is no other instance running, delete %s" % lockfile
        sys.exit(1)

    f = file(lockfile, 'w')
    f.write("PID: %s\n" % os.getpid())
    f.close()

    try:
        if options.doc:
            plugin.print_doc(options.doc)
        elif options.list:
            plugin.print_list(options)
        elif options.failed:
            manager.print_failed()
        elif options.clear_failed:
            manager.clear_failed()
        else:
            manager.execute()
    finally:
        os.remove(lockfile)
