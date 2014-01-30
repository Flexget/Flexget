from __future__ import unicode_literals, division, absolute_import
import os
import logging
import re

import urlparse
import xmlrpclib
from flexget import plugin
from flexget.event import event
from flexget.entry import Entry

log = logging.getLogger('aria2')

# TODO: stop using torrent_info_hash[0:16] as the GID

# for RENAME_CONTENT_FILES:
# to rename TV episodes, content_is_episodes must be set to yes

class OutputAria2(object):

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
                'default': ['.mkv','.avi','.mp4','.wmv','.asf','.divx','.mov','.mpg','.rm']
            },
            'aria_config': {
                'type': 'object',
                'additionalProperties': {'oneOf': [{'type': 'string'}, {'type': 'integer'}]}
            }
            
        },
        'required': ['do', 'server', 'port'],
        'additionalProperties': False
    }

    def on_task_output(self, task, config):
        if 'uri' not in config and config['do'] == 'add-new':
            raise plugin.PluginError('uri (path to folder containing file(s) on server) is required when adding new '
                                     'downloads.', log)
        if 'dir' not in config['aria_config'] and config['do'] == 'add-new':
            raise plugin.PluginError('dir (destination directory) is required.', log)
        if config['keep_parent_folders'] and config['aria_config']['dir'].find('{{parent_folders}}') == -1:
            raise plugin.PluginError('When using keep_parent_folders, you must specify {{parent_folders}} in the dir '
                                     'option to show where it goes.', log)
        if config['rename_content_files'] == True and config['rename_template'] == '':
            raise plugin.PluginError('When using rename_content_files, you must specify a rename_template.', log)
        if len(config['username']) > 0 and len(config['password']) == 0:
            raise plugin.PluginError('If you specify an aria2 username, you must specify a password.')

        try:
            if len(config['username']) > 0:
                userpass = '%s:%s@' % (config['username'], config['password'])
            else:
                userpass = ''
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
        except socket.err as err:
            raise plugin.PluginError('Socket connection issue with aria2 daemon at %s: %s'
                                      % (baseurl, err.strerror), log)
        except:
            raise plugin.PluginError('Unidentified error during connection to aria2 daemon at %s' % baseurl, log)


        # loop entries
        for entry in task.accepted:
            entry['basedir'] = config['aria_config']['dir']
            if 'aria_gid' in entry:
                config['aria_config']['gid'] = entry['aria_gid']
            elif 'torrent_info_hash' in entry:
                config['aria_config']['gid'] = entry['torrent_info_hash'][0:16]
            else:
                config['aria_config']['gid'] = ''

            if 'content_files' not in entry:
                if entry['url']:
                    entry['content_files'] = [entry['url']]
                else:
                    entry['content_files'] = [entry['title']]

            counter = 0
            for curFile in entry['content_files']:

                curFilename = curFile.split('/')[-1]
                if curFile.split('/')[0] != curFilename and config['keep_parent_folders']:
                    lastSlash = curFile.rfind('/')
                    curPath = curFile[:lastSlash]
                    if curPath[0:1] == '/':
                        curPath = curPath[1:]
                    if entry['basedir'][-1:] != '/':
                        entry['basedir'] = entry['basedir'] + '/'
                    entry['parent_folders'] = entry['basedir'] + curPath

                fileDot = curFilename.rfind(".")
                fileExt = curFilename[fileDot:]

                if len(entry['content_files']) > 1:
                    # if there is more than 1 file, need to give unique gids, this will work up to 999 files
                    counter += 1
                    strCounter = str(counter)
                    if len(entry['content_files']) > 99:
                        # sorry not sorry if you have more than 999 files
                        config['aria_config']['gid'] = config['aria_config']['gid'][0:-3] + strCounter.rjust(3,str('0'))
                    else:
                        config['aria_config']['gid'] = config['aria_config']['gid'][0:-2] + strCounter.rjust(2,str('0'))

                if config['exclude_samples'] == True:
                    # remove sample files from download list
                    if curFilename.lower().find('sample') > -1:
                        continue

                if fileExt not in config['file_exts']:
                    if config['exclude_non_content'] == True:
                        # don't download non-content files, like nfos - definable in file_exts
                        continue

                if config['parse_filename']:
                    if config['content_is_episodes']:
                        metainfo_series = plugin.get_plugin_by_name('metainfo_series')
                        guess_series = metainfo_series.instance.guess_series
                        if guess_series(curFilename):
                            parser = guess_series(curFilename)
                            entry['series_name'] = parser.name
                            # if the last four chars are numbers, REALLY good chance it's actually a year...
                            #fix it if so desired
                            log.verbose(entry['series_name'])
                            if re.search(r'\d{4}', entry['series_name'][-4:]) is not None and config['fix_year']:
                                entry['series_name'] = entry['series_name'][0:-4] +'('+ entry['series_name'][-4:] + ')'
                                log.verbose(entry['series_name'])
                            parser.data = curFilename
                            parser.parse
                            log.debug(parser.id_type)
                            if parser.id_type == 'ep':
                                entry['series_id'] = 'S' + str(parser.season).rjust(2, str('0')) + 'E'
                                entry['series_id'] += str(parser.episode).rjust(2, str('0'))
                            elif parser.id_type == 'sequence':
                                entry['series_id'] = parser.episode
                            elif parser.id_type and parser.id:
                                entry['series_id'] = parser.id
                    else:
                        from flexget.utils.titles.movie import MovieParser
                        parser = MovieParser()
                        parser.data = curFile
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
                        entry['year'] = parser.year
                        entry['movie_year'] = parser.year
                        

                if config['rename_content_files'] == True:
                    if config['content_is_episodes']:
                        if config['rename_template'].find('series_name') > -1 and 'series_name' not in entry:
                            raise plugin.PluginError('Unable to parse series_name and used in rename_template.', log)
                        elif config['rename_template'].find('series_id') > -1 and 'series_id' not in entry:
                            raise plugin.PluginError('Unable to parse series id and used in rename_template.', log)
                        config['aria_config']['out'] = entry.render(config['rename_template']) + fileExt
                        log.verbose(config['aria_config']['out'])
                    else:
                        if (('name' not in entry and config['rename_template'].find('name') > -1) or
                           ('movie_name' not in entry and config['rename_template'].find('movie_name') > -1)):
                            raise plugin.PluginError('Unable to parse movie name (%s). Try enabling imdb_lookup in this'
                                                     ' task to assist.' % curFile, log)
                        else:
                            config['aria_config']['out'] = entry.render(config['rename_template']) + fileExt
                            log.verbose(config['aria_config']['out'])
                else:
                    config['aria_config']['out'] = curFilename
                                    
                if config['do'] == 'add-new':
                    newDownload = 0
                    try:
                        r = s.aria2.tellStatus(config['aria_config']['gid'], ['gid', 'status'])
                        log.info('Download status for %s (gid %s): %s' % (entry['title'], r['gid'], r['status']))
                        if r['status'] == 'paused':
                            try:
                                if not task.manager.options.test:
                                    s.aria2.unpause(r['gid'])
                                log.info('  Unpaused download.')
                            except xmlrpclib.Fault as err:
                                raise plugin.PluginError('aria response to unpause request: %s' % err.faultString, log)
                        else:
                            log.info('  Therefore, not re-adding.')
                    except xmlrpclib.Fault as err:
                        if err.faultString[-12:] == 'is not found':
                            newDownload = 1
                        else:
                            raise plugin.PluginError('aria response to download status request: %s'
                                                      % err.faultString, log)
                    except xmlrpclib.ProtocolError as err:
                        raise plugin.PluginError('Could not connect to aria2 at %s. Protocol error %s: %s'
                                                  % (baseurl, err.errcode, err.errmsg), log)

                    if newDownload == 1:
                        try:
                            entry['filename'] = curFile
                            curUri = entry.render(config['uri'])
                            if not task.manager.options.test:
                                r = s.aria2.addUri([curUri], dict((key, entry.render(str(value))) for (key, value) in config['aria_config'].iteritems()))
                            else:
                                if config['aria_config']['gid'] == '':
                                    r = '1234567890123456'
                                else:
                                    r = config['aria_config']['gid']
                            log.info('%s successfully added to aria2 with gid %s.' % (config['aria_config']['out'], r))
                            log.verbose('uri: %s' % curUri)
                        except xmlrpclib.Fault as err:
                            raise plugin.PluginError('aria response to add URI request: %s' % err.faultString, log)


                elif config['do'] == 'remove-completed':
                    try:
                        r = s.aria2.tellStatus(config['aria_config']['gid'], ['gid', 'status'])
                        log.info('Status of download with gid %s: %s' % (r['gid'], r['status']))
                        if r['status'] == 'complete' or r['status'] == 'removed':
                            if not task.manager.options.test:
                                try:
                                    a = s.aria2.removeDownloadResult(r['gid'])
                                    if a == 'OK':
                                        log.info('Download with gid %s removed from memory' % r['gid'])
                                except xmlrpclib.Fault as err:
                                    raise plugin.PluginError('aria response to remove request: %s'
                                                              % err.faultString, log)
                        else:
                            log.info('Download with gid %s could not be removed because of its status: %s'
                                      % (r['gid'], r['status']))
                    except xmlrpclib.Fault as err:
                        if err.faultString[-12:] == 'is not found':
                            log.warning('Download with gid %s could not be removed because it was not found. It was '
                                        'possibly previously removed or never added.' % config['aria_config']['gid'])
                        else:
                            raise plugin.PluginError('aria response to status request: %s' % err.faultString, log)


@event('plugin.register')
def register_plugin():
    plugin.register(OutputAria2, 'aria2', api_ver=2)
