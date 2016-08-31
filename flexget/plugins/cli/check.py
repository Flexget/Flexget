from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin

import codecs
import logging
import yaml

from flexget import options
from flexget.event import event
from flexget.terminal import console

log = logging.getLogger('check')


@event('manager.before_config_load')
def before_config_load(manager):
    if manager.options.cli_command == 'check':
        pre_check_config(manager.config_path)


def pre_check_config(config_path):
    """Checks configuration file for common mistakes that are easily detectable"""
    with codecs.open(config_path, 'r', 'utf-8') as config_file:
        try:
            config = config_file.read()
        except UnicodeDecodeError:
            return

    def get_indentation(line):
        i, n = 0, len(line)
        while i < n and line[i] == ' ':
            i += 1
        return i

    def isodd(n):
        return bool(n % 2)

    line_num = 0
    duplicates = {}
    # flags
    prev_indentation = 0
    prev_mapping = False
    prev_list = True
    prev_scalar = True
    list_open = False  # multiline list with [

    for line in config.splitlines():
        if '# warnings off' in line.strip().lower():
            log.debug('config pre-check warnings off')
            break
        line_num += 1
        # remove linefeed
        line = line.rstrip()
        # empty line
        if line.strip() == '':
            continue
        # comment line
        if line.strip().startswith('#'):
            continue
        indentation = get_indentation(line)

        if prev_scalar:
            if indentation <= prev_indentation:
                prev_scalar = False
            else:
                continue

        cur_list = line.strip().startswith('-')

        # skipping lines as long as multiline compact list is open
        if list_open:
            if line.strip().endswith(']'):
                list_open = False
                # print 'closed list at line %s' % line
            continue
        else:
            list_open = line.strip().endswith(': [') or line.strip().endswith(':[')
            if list_open:
                # print 'list open at line %s' % line
                continue

                # print '#%i: %s' % (line_num, line)
                # print 'indentation: %s, prev_ind: %s, prev_mapping: %s, prev_list: %s, cur_list: %s' % \
                #        (indentation, prev_indentation, prev_mapping, prev_list, cur_list)

        if ':\t' in line:
            log.critical('Line %s has TAB character after : character. '
                         'DO NOT use tab key when editing config!' % line_num)
        elif '\t' in line:
            log.warning('Line %s has tabs, use only spaces!' % line_num)
        if isodd(indentation):
            log.warning('Config line %s has odd (uneven) indentation' % line_num)
        if indentation > prev_indentation and not prev_mapping:
            # line increases indentation, but previous didn't start mapping
            log.warning('Config line %s is likely missing \':\' at the end' % (line_num - 1))
        if indentation > prev_indentation + 2 and prev_mapping and not prev_list:
            # mapping value after non list indented more than 2
            log.warning('Config line %s is indented too much' % line_num)
        if indentation <= prev_indentation + (2 * (not cur_list)) and prev_mapping and prev_list:
            log.warning('Config line %s is not indented enough' % line_num)
        if prev_mapping and cur_list:
            # list after opening mapping
            if indentation < prev_indentation or indentation > prev_indentation + 2 + (2 * prev_list):
                log.warning('Config line %s containing list element is indented incorrectly' % line_num)
        elif prev_mapping and indentation <= prev_indentation:
            # after opening a map, indentation doesn't increase
            log.warning('Config line %s is indented incorrectly (previous line ends with \':\')' % line_num)

        # notify if user is trying to set same key multiple times in a task (a common mistake)
        for level in duplicates.keys():
            # when indentation goes down, delete everything indented more than that
            if indentation < level:
                duplicates[level] = {}
        if ':' in line:
            name = line.split(':', 1)[0].strip()
            ns = duplicates.setdefault(indentation, {})
            if name in ns:
                log.warning('Trying to set value for `%s` in line %s, but it is already defined in line %s!' %
                            (name, line_num, ns[name]))
            ns[name] = line_num

        prev_indentation = indentation
        # this line is a mapping (ends with :)
        prev_mapping = line[-1] == ':'
        prev_scalar = line[-1] in '|>'
        # this line is a list
        prev_list = line.strip()[0] == '-'
        if prev_list:
            # This line is in a list, so clear the duplicates,
            # as duplicates are not always wrong in a list. see #697
            duplicates[indentation] = {}

    log.verbose('Pre-checked %s configuration lines' % line_num)


def check(manager, options):
    log.verbose('Checking config file `%s`' % manager.config_path)
    if manager.is_daemon:
        # If we are running in a daemon, check disk config
        pre_check_config(manager.config_path)
        with codecs.open(manager.config_path, 'r', encoding='utf-8') as config_file:
            try:
                config = yaml.load(config_file)
            except yaml.error.YAMLError as e:
                log.critical('Config file is invalid YAML:')
                for line in str(e).split('\n'):
                    console(line)
                return
            try:
                manager.validate_config(config)
            except ValueError as e:
                for error in getattr(e, 'errors', []):
                    log.critical("[%s] %s", error.json_pointer, error.message)
            else:
                log.verbose('Config passed check.')
    else:
        # If we aren't in a daemon, the config already validated if we got here
        log.verbose('Config passed check.')


@event('options.register')
def register_options():
    options.register_command('check', check, help='validate configuration file and print errors')
