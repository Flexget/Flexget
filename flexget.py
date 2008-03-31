#!/usr/bin/python2.5

from manager import Manager

if __name__ == "__main__":
    manager = Manager()
    if manager.options.doc:
        manager.print_module_doc()
    elif manager.options.list:
        manager.print_module_list()
    elif manager.options.failed:
        manager.print_failed()
    elif manager.options.clear_failed:
        manager.clear_failed()
    else:
        manager.execute()
