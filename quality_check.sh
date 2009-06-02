#!/bin/sh
pychecker --no-argsused --no-shadowbuiltin --only --limit=40 flexget/*.py flexget/plugins/*.py
