""" Plugin package to place local private extensions in.

    Use this to avoid naming conflicts with standard plugins and place your
    own private plugins in "~/.flexget/plugins/local". It's also a good idea
    to start their names with "local_", i.e. use code like this::
    
        from flexget import plugin
    
        class LocalPlugin(plugin.Plugin):
            ...
"""
