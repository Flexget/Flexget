from __future__ import unicode_literals, division, absolute_import
import os
import logging
import re
import urlparse
import xmlrpclib

from flexget import plugin
from flexget.event import event
from flexget.entry import Entry
from flexget.utils.template import RenderError
from flexget.plugin import get_plugin_by_name

from socket import error as socket_error

log = logging.getLogger('aria2')

# TODO: stop using torrent_info_hash[0:16] as the GID

# for RENAME_CONTENT_FILES:
# to rename TV episodes, content_is_episodes must be set to yes


class OutputAria2(object):

    """
    aria2 output plugin
    Version 1.0.0
    
    Configuration:
    server:     Where aria2 daemon is running. default 'localhost'
    port:       Port of that server. default '6800'
    username:   XML-RPC username set in aria2. default ''
    password:   XML-RPC password set in aria2. default ''
    do:         [add-new|remove-completed] What action to take with incoming
                entries.
    uri:        URI of file to download. Can include inline Basic Auth para-
                meters and use jinja2 templating with any fields available
                in the entry. If you are using any of the dynamic renaming
                options below, the filename can be included in this setting
                using {{filename}}.
    exclude_samples:
                [yes|no] Exclude any files that include the word 'sample' in
                their name. default 'no'
    exclude_non_content:
                [yes|no] Exclude any non-content files, as defined by filename
                extensions not listed in file_exts. (See below.) default 'no'
    rename_content_files:
                [yes|no] If set, rename all content files (as defined by
                extensions listed in file_exts). default 'no'
    rename_template:
                If set, and rename_content_files is yes, all content files
                will be renamed using the value of this field as a template.
                Will be parsed with jinja2 and can include any fields
                available in the entry. default ''
    parse_filename:
                [yes|no] If yes, filenames will be parsed with either the
                series parser (if content_is_episodes is set to yes) or the
                movie parser. default: 'no'
    content_is_episodes:
                [yes|no] If yes, files will be parsed by the series plugin
                parser to attempt to determine series name and series_id. If
                no, files will be treated as movies. Note this has no effect
                unless parse_filename is set to yes. default 'no'
    keep_parent_folders:
                [yes|no] If yes, any parent folders within the torrent itself
                will be kept and created within the download directory.
                For example, if a torrent has this structure:
                MyTorrent/
                  MyFile.mkv
                If this is set to yes, the MyTorrent folder will be created in
                the download directory. If set to no, the folder will be
                ignored and the file will be downloaded directly into the
                download directory. default: 'no'
    fix_year:   [yes|no] If yes, and the last four characters of the series
                name are numbers, enclose them in parantheses as they are
                likely a year. Example: Show Name 1995 S01E01.mkv would become
                Show Name (1995) S01E01.mkv. default 'yes'
    file_exts:  [list] File extensions of all files considered to be content
                files. Used to determine which files to rename or which files
                to exclude from download, with appropriate options set. (See
                above.)
                default: ['.mkv', '.avi', '.mp4', '.wmv', '.asf', '.divx',
                '.mov', '.mpg', '.rm']
    aria_config:
                "Parent folder" for any options to be passed directly to aria.
                Any command line option listed at
                http://aria2.sourceforge.net/manual/en/html/aria2c.html#options
                can be used by removing the two dashes (--) in front of the 
                command name, and changing key=value to key: value. All
                options will be treated as jinja2 templates and rendered prior
                to passing to aria2. default ''

    Sample configuration:
    aria2:
      server: myserver
      port: 6802
      do: add-new
      exclude_samples: yes
      exclude_non_content: yes
      parse_filename: yes
      content_is_episodes: yes
      rename_content_files: yes
      rename_template: '{{series_name}} - {{series_id||lower}}'
      aria_config:
        max-connection-per-server: 4
        max-concurrent-downloads: 4
        split: 4
        file-allocation: none
        dir: "/Volumes/all_my_tv/{{series_name}}"
    """

    schema = {
        'type': 'object',
        'properties': {
            'server': {'type': 'string', 'default': 'localhost'},
            'port': {'type': 'integer', 'default': 6800},
            'username': {'type': 'string', 'default': ''},
            'password': {'type': 'string', 'default': ''},
            'do': {'type': 'string', 'enum': ['add-new', 'remove-completed']},
            'uri': {'type': 'string'},
            'exclude_samples': {'type': 'boolean', 'default': False},
            'exclude_non_content': {'type': 'boolean', 'default': True},
            'rename_content_files': {'type': 'boolean', 'default': False},
            'content_is_episodes': {'type': 'boolean', 'default': False},
            'keep_parent_folders': {'type': 'boolean', 'default': False},
            'parse_filename': {'type': 'boolean', 'default': False},
            'fix_year': {'type': 'boolean', 'default': True},
            'rename_template': {'type': 'string', 'default': ''},
            'file_exts': {
                'type': 'array',
                'items': {'type': 'string'},
                'default': ['.mkv', '.avi', '.mp4', '.wmv', '.asf', '.divx', '.mov', '.mpg', '.rm']
            },
            'aria_config': {
                'type': 'object',
                'additionalProperties': {'oneOf': [{'type': 'string'}, {'type': 'integer'}]}
            }

        },
        'required': ['do'],
        'additionalProperties': False
    }

    def on_task_output(self, task, config):
        if 'aria_config' not in config:
            config['aria_config'] = {}
        if 'uri' not in config and config['do'] == 'add-new':
            raise plugin.PluginError('uri (path to folder containing file(s) on server) is required when adding new '
                                     'downloads.', log)
        if 'dir' not in config['aria_config']:
            if config['do'] == 'add-new':
                raise plugin.PluginError('dir (destination directory) is required.', log)
            else:
                config['aria_config']['dir'] = ''
        if config['keep_parent_folders'] and config['aria_config']['dir'].find('{{parent_folders}}') == -1:
            raise plugin.PluginError('When using keep_parent_folders, you must specify {{parent_folders}} in the dir '
                                     'option to show where it goes.', log)
        if config['rename_content_files'] and not config['rename_template']:
            raise plugin.PluginError('When using rename_content_files, you must specify a rename_template.', log)
        if config['username'] and not config['password']:
            raise plugin.PluginError('If you specify an aria2 username, you must specify a password.')

        try:
            userpass = ''
            if config['username']:
                userpass = '%s:%s@' % (config['username'], config['password'])
            baseurl = 'http://%s%s:%s/rpc' % (userpass, config['server'], config['port'])
            log.debug('base url: %s' % baseurl)
            s = xmlrpclib.ServerProxy(baseurl)
            log.info('Connected to daemon at ' + baseurl + '.')
        except xmlrpclib.ProtocolError as err:
            raise plugin.PluginError('Could not connect to aria2 at %s. Protocol error %s: %s'
                                     % (baseurl, err.errcode, err.errmsg), log)
        except xmlrpclib.Fault as err:
            raise plugin.PluginError('XML-RPC fault: Unable to connect to aria2 daemon at %s: %s'
                                     % (baseurl, err.faultString), log)
        except socket_error as (error, msg):
            raise plugin.PluginError('Socket connection issue with aria2 daemon at %s: %s'
                                     % (baseurl, msg), log)
        except:
            raise plugin.PluginError('Unidentified error during connection to aria2 daemon at %s' % baseurl, log)

        # loop entries
        for entry in task.accepted:
            config['aria_dir'] = config['aria_config']['dir']
            if 'aria_gid' in entry:
                config['aria_config']['gid'] = entry['aria_gid']
            elif 'torrent_info_hash' in entry:
                config['aria_config']['gid'] = entry['torrent_info_hash'][0:16]
            elif 'gid' in config['aria_config']:
                del(config['aria_config']['gid'])

            if 'content_files' not in entry:
                if entry['url']:
                    entry['content_files'] = [entry['url']]
                else:
                    entry['content_files'] = [entry['title']]
            else:
                if not isinstance(entry['content_files'], list):
                    entry['content_files'] = [entry['content_files']]

            counter = 0
            for cur_file in entry['content_files']:
                entry['parent_folders'] = ''
                # reset the 'dir' or it will only be rendered on the first loop
                config['aria_config']['dir'] = config['aria_dir']

                cur_filename = cur_file.split('/')[-1]
                if cur_file.split('/')[0] != cur_filename and config['keep_parent_folders']:
                    lastSlash = cur_file.rfind('/')
                    cur_path = cur_file[:lastSlash]
                    if cur_path[0:1] == '/':
                        cur_path = cur_path[1:]
                    entry['parent_folders'] = cur_path
                    log.debug('parent folders: %s' % entry['parent_folders'])

                file_dot = cur_filename.rfind(".")
                file_ext = cur_filename[file_dot:]

                if len(entry['content_files']) > 1 and 'gid' in config['aria_config']:
                    # if there is more than 1 file, need to give unique gids, this will work up to 999 files
                    counter += 1
                    strCounter = str(counter)
                    if len(entry['content_files']) > 99:
                        # sorry not sorry if you have more than 999 files
                        config['aria_config']['gid'] = ''.join([config['aria_config']['gid'][0:-3],
                                                               strCounter.rjust(3, str('0'))])
                    else:
                        config['aria_config']['gid'] = ''.join([config['aria_config']['gid'][0:-2],
                                                               strCounter.rjust(2, str('0'))])

                if config['exclude_samples'] == True:
                    # remove sample files from download list
                    if cur_filename.lower().find('sample') > -1:
                        continue

                if file_ext not in config['file_exts']:
                    if config['exclude_non_content'] == True:
                        # don't download non-content files, like nfos - definable in file_exts
                        continue

                if config['parse_filename']:
                    if config['content_is_episodes']:
                        metainfo_series = plugin.get_plugin_by_name('metainfo_series')
                        guess_series = metainfo_series.instance.guess_series
                        if guess_series(cur_filename):
                            parser = guess_series(cur_filename)
                            entry['series_name'] = parser.name
                            # if the last four chars are numbers, REALLY good chance it's actually a year...
                            # fix it if so desired
                            log.verbose(entry['series_name'])
                            if re.search(r'\d{4}', entry['series_name'][-4:]) is not None and config['fix_year']:
                                entry['series_name'] = ''.join([entry['series_name'][0:-4], '(',
                                                               entry['series_name'][-4:], ')'])
                                log.verbose(entry['series_name'])
                            parser.data = cur_filename
                            parser.parse
                            log.debug(parser.id_type)
                            if parser.id_type == 'ep':
                                entry['series_id'] = ''.join(['S', str(parser.season).rjust(2, str('0')), 'E',
                                                             str(parser.episode).rjust(2, str('0'))])
                            elif parser.id_type == 'sequence':
                                entry['series_id'] = parser.episode
                            elif parser.id_type and parser.id:
                                entry['series_id'] = parser.id
                    else:
                        parser = get_plugin_by_name('parsing').instance.parse_movie(cur_filename)
                        parser.parse()
                        log.info(parser)
                        testname = parser.name
                        testyear = parser.year
                        parser.data = entry['title']
                        parser.parse()
                        log.info(parser)
                        if len(parser.name) > len(testname):
                            entry['name'] = parser.name
                            entry['movie_name'] = parser.name
                        else:
                            entry['name'] = testname
                            entry['movie_name'] = testname
                        if parser.year:
                            entry['year'] = parser.year
                            entry['movie_year'] = parser.year
                        else:
                            entry['year'] = testyear
                            entry['movie_year'] = testyear

                if config['rename_content_files']:
                    if config['content_is_episodes']:
                        try:
                            config['aria_config']['out'] = entry.render(config['rename_template']) + file_ext
                            log.verbose(config['aria_config']['out'])
                        except RenderError as e:
                            log.error('Could not rename file %s: %s.' % (cur_filename, e))
                            continue
                    else:
                        try:
                            config['aria_config']['out'] = entry.render(config['rename_template']) + file_ext
                            log.verbose(config['aria_config']['out'])
                        except RenderError as e:
                            log.error('Could not rename file %s: %s. Try enabling imdb_lookup in this task'
                                      ' to assist.' % (cur_filename, e))
                            continue
                elif 'torrent_info_hash' not in entry: 
                    config['aria_config']['out'] = cur_filename

                if config['do'] == 'add-new':
                    log.debug('Adding new file')
                    new_download = 0
                    if 'gid' in config['aria_config']:
                        try:
                            r = s.aria2.tellStatus(config['aria_config']['gid'], ['gid', 'status'])
                            log.info('Download status for %s (gid %s): %s' % (
                                config['aria_config'].get('out', config['uri']), r['gid'],
                                r['status']))
                            if r['status'] == 'paused':
                                try:
                                    if not task.manager.options.test:
                                        s.aria2.unpause(r['gid'])
                                    log.info('  Unpaused download.')
                                except xmlrpclib.Fault as err:
                                    raise plugin.PluginError(
                                        'aria2 response to unpause request: %s' % err.faultString, log)
                            else:
                                log.info('  Therefore, not re-adding.')
                        except xmlrpclib.Fault as err:
                            if err.faultString[-12:] == 'is not found':
                                new_download = 1
                            else:
                                raise plugin.PluginError('aria2 response to download status request: %s'
                                                         % err.faultString, log)
                        except xmlrpclib.ProtocolError as err:
                            raise plugin.PluginError('Could not connect to aria2 at %s. Protocol error %s: %s'
                                                     % (baseurl, err.errcode, err.errmsg), log)
                        except socket_error as (error, msg):
                            raise plugin.PluginError('Socket connection issue with aria2 daemon at %s: %s'
                                                     % (baseurl, msg), log)
                    else:
                        new_download = 1

                    if new_download == 1:
                        try:
                            entry['filename'] = cur_file
                            cur_uri = entry.render(config['uri'])
                            log.verbose('uri: %s' % cur_uri)
                        except RenderError as e:
                            raise plugin.PluginError('Unable to render uri: %s' % e)
                        try:
                            for key, value in config['aria_config'].iteritems():
                                log.trace('rendering %s: %s' % (key, value))
                                config['aria_config'][key] = entry.render(unicode(value))
                            log.debug('dir: %s' % config['aria_config']['dir'])
                            if not task.manager.options.test:
                                r = s.aria2.addUri([cur_uri], config['aria_config'])
                            else:
                                if 'gid' not in config['aria_config']:
                                    r = '1234567890123456'
                                else:
                                    r = config['aria_config']['gid']
                            log.info('%s successfully added to aria2 with gid %s.' % (
                                config['aria_config'].get('out', config['uri']),
                                r))
                        except xmlrpclib.Fault as err:
                            raise plugin.PluginError('aria2 response to add URI request: %s' % err.faultString, log)
                        except socket_error as (error, msg):
                            raise plugin.PluginError('Socket connection issue with aria2 daemon at %s: %s'
                                                     % (baseurl, msg), log)
                        except RenderError as e:
                            raise plugin.PluginError('Unable to render one of the fields being passed to aria2:'
                                                     '%s' % e)

                elif config['do'] == 'remove-completed':
                    try:
                        r = s.aria2.tellStatus(config['aria_config']['gid'], ['gid', 'status'])
                        log.info('Status of download with gid %s: %s' % (r['gid'], r['status']))
                        if r['status'] in ['complete', 'removed']:
                            if not task.manager.options.test:
                                try:
                                    a = s.aria2.removeDownloadResult(r['gid'])
                                    if a == 'OK':
                                        log.info('Download with gid %s removed from memory' % r['gid'])
                                except xmlrpclib.Fault as err:
                                    raise plugin.PluginError('aria2 response to remove request: %s'
                                                             % err.faultString, log)
                                except socket_error as (error, msg):
                                    raise plugin.PluginError('Socket connection issue with aria2 daemon at %s: %s'
                                                             % (baseurl, msg), log)
                        else:
                            log.info('Download with gid %s could not be removed because of its status: %s'
                                     % (r['gid'], r['status']))
                    except xmlrpclib.Fault as err:
                        if err.faultString[-12:] == 'is not found':
                            log.warning('Download with gid %s could not be removed because it was not found. It was '
                                        'possibly previously removed or never added.' % config['aria_config']['gid'])
                        else:
                            raise plugin.PluginError('aria2 response to status request: %s' % err.faultString, log)
                    except socket_error as (error, msg):
                        raise plugin.PluginError('Socket connection issue with aria2 daemon at %s: %s'
                                                 % (baseurl, msg), log)


@event('plugin.register')
def register_plugin():
    plugin.register(OutputAria2, 'aria2', api_ver=2)
