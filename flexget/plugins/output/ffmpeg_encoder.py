import logging
import os
from flexget import plugin
import subprocess
import tempfile
import string
import time
import datetime
import shutil
from flexget.utils.template import RenderError
from flexget.event import event

log = logging.getLogger("ffmpeg_encoder")

class FFMPEGEncoder(object):
    
    specific_codec_options = {
        'type' : 'object',
        'properties' : {
            'codec_type' : { 'type' : 'string'},
            'original_codec_requirements' : {
                'type' : 'object',
                'properties' : {
                    'original_codec' :  { 'type' : 'string'},
                    'min_bitrate' : {'type' : 'integer'},
                    'max_bitrate' : {'type' : 'integer'},
                    'minimum_channels' : {'type' : 'integer'},
                    'maximum_channels' : {'type' : 'integer'}
                },
                'additionalProperties' : False
            },
            'codec' : { 'type' : 'string'},
            'bitrate' : {'type' : 'integer'},
            'channels' : {'type' : 'integer'}
        },
        'additionalProperties' : False                      
    }
    
    language_list = {
        'type' : 'object',
        'properties' : {
            'language' : {'type' : 'string'},
            'codec_type' : {'type' : 'string'}
        },
        'additionalProperties' : False
    }
    
    schema = {
        'type' : 'object',
        'properties' : {
            'output_dir' : { 'type' : 'string', 'format' : 'path'},
            'filename' : { 'type' : 'string' },
            'video_encoding_options' : {
                'type' : 'object',
                'properties' : {
                    'codec' : {'type' : 'string', 'default' : 'copy'},
                },
                'additionalProperties' : False
            },
            'default_language' : {'type' : 'string', 'default' : 'eng'},
            'temp_dir' : {'type' : 'string', 'format' : 'path'},
            'audio_encoding_options' : {
                'type' : 'object',
                'properties' : {
                    'codec' : {'type' : 'string', 'default' : 'copy'},
                    'bitrate' : {'type' : 'integer'},
                    'channels' : {'type' : 'integer'}
                },
                'additionalProperties' : False
            },
            'subtitles_encoding_options' : {
                'type' : 'object',
                'properties' : {
                    'codec' : {'type' : 'string', 'default' : 'copy'},
                },
                'additionalProperties' : False
            },
            'language_specific_options' : {
                'type' : 'array',
                'items' : {
                    'oneOf' : [
                        {
                            'type' : 'object',
                            'properties' : {
                                'languages_to_include' : {'type' : 'array', "items": {"type": "string"}},
                                'codec_options' : specific_codec_options
                            },
                            'additionalProperties' : False
                        },{
                            'type' : 'object',
                            'properties' : {
                                'languages_to_exclude' : {'type' : 'array', "items": {"type": "string"}},
                                'codec_options' : specific_codec_options
                            },
                            'additionalProperties' : False
                        }
                    ]
                }
            },
            'specific_codec_options' : {
                'type' : 'array',
                'items' : specific_codec_options
            },
            'languages_to_exclude' : {
                'type' : 'array',
                'items' : language_list
            },
            'languages_to_include' : {
                'type' : 'array',
                'items' : language_list
            }
        },
        'additionalProperties' : False
    }
    
    def prepare_config(self, config):
        
        # We first make dictionary of languages to include
        # and to exclude for each codec types
        if not 'languages_to_include' in config:
            self.include_all_languages = True
        else:
            self.include_all_languages = False
            self.language_to_include = {
                'video' : [],
                'audio' : [],
                'subtitle' : []       
            }
            for current_language_to_include in config['languages_to_include']:
                if not 'language' in current_language_to_include:
                    continue
                language = current_language_to_include['language']
                if 'codec_type' in current_language_to_include:
                    self.language_to_include[current_language_to_include['codec_type']].append(language)
                else:
                    for key in self.language_to_include:
                        self.language_to_include[key].append(language)
                    
        self.language_to_exclude = {
                'video' : [],
                'audio' : [],
                'subtitle' : []       
            }
        if 'languages_to_exclude' in config:
            for current_language_to_exclude in config['languages_to_exclude']:
                if not 'language' in current_language_to_exclude:
                    continue
                language = current_language_to_exclude['language']
                if 'codec_type' in current_language_to_exclude:
                    self.language_to_exclude[current_language_to_exclude['codec_type']].append(language)
                else:
                    for key in self.language_to_include:
                        self.language_to_exclude[key].append(language)
    
    def on_task_start(self, task, config):
        def which(program):
            def is_exe(fpath):
                return os.path.isfile(fpath) and os.access(fpath, os.X_OK)

            fpath, fname = os.path.split(program)
            if fpath:
                if is_exe(program):
                    return program
            else:
                for path in os.environ["PATH"].split(os.pathsep):
                    path = path.strip('"')
                    exe_file = os.path.join(path, program)
                    if is_exe(exe_file):
                        return exe_file

            return None
        
        self.ffprobe = which("ffprobe")
        if self.ffprobe is None:
            raise plugin.DependencyError("ffprobe is required for this module to work. Please install it")
        
        self.ffpmeg = which("ffmpeg")
        if self.ffpmeg is None:
            raise plugin.DependencyError("ffprobe is required for this module to work. Please install it")
        
        self.prepare_config(config)
        
    def on_task_output(self, task, config):
        for entry in task.accepted:
            if not 'location' in entry:
                entry.reject("%s can't be found" % entry['title'])
            elif not os.path.exists(entry['location']):
                entry.reject("%s can't be found" % entry['title'])
            else:
                
                src_filename = os.path.basename(entry['location'])
                log.debug("Analyzing %s" % src_filename)
                p = subprocess.Popen([self.ffprobe,'-show_streams','-of','compact',entry['location']],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
                out = p.communicate()[0]
                if not out:
                    entry.reject("%s isn't a media file" % entry["location"])
                else:
                    streams = out.rstrip().split('\n')
                    command = {
                               'commands': [
                                            self.ffpmeg,
                                            "-i",
                                            entry['location']
                                ],
                               'audio_number': 0,
                               'video_number': 0,
                               'subtitle_number': 0,
                               'total_streams': 0,
                    }
                    for current_stream in streams:
                        self.analyse_stream(current_stream, command, config)
                    
                    filename_without_ext = os.path.splitext(src_filename)[0]
                    
                    if 'filename' in config:
                        try:
                            dst_filename = entry.render(config['filename'])
                            dst_filename = dst_filename + ".mkv"
                        except RenderError as e:
                            entry.fail("Unable to process output file name : %s" % e)
                    else:
                        dst_filename = filename_without_ext + ".mkv"
                    command["commands"].append("-threads")
                    command["commands"].append("0")
                    if 'temp_dir' in config:
                        if os.path.isdir(config['temp_dir']):
                            tmp_dir = config['temp_dir']
                        else:
                            log.error("%s is not a directory, using system temp dir" % config['temp_dir'])
                            tmp_dir = tempfile.gettempdir()
                    else:
                        tmp_dir = tempfile.gettempdir()
                        
                    tmpfile = os.path.join(tmp_dir,dst_filename)
                    command["commands"].append(tmpfile)
                    log.info("Encoding %s to %s with command %s" % (src_filename,tmpfile,string.join(command["commands"], " ")))
                    ts = time.time()
                    pipe2 = subprocess.Popen(command["commands"],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
                    error = pipe2.communicate()[1]
                    return_code = pipe2.returncode
                    te = time.time()
                    if return_code == 0:
                        log.info("Encoding of %s succeeded in %s" % (src_filename,str(datetime.timedelta(seconds=te-ts))))
                        if 'output_dir' in config:
                            shutil.move(tmpfile, os.path.join(config['output_dir'],os.path.basename(tmpfile)))
                    else:
                        entry.fail("Encoding failed with error %s" % error)
                        os.remove(tmpfile)
                    
    def analyse_stream(self,stream,command,config):
        hashed_stream={}
        parsed_stream = stream.rstrip().split('|')
        for stream_element in parsed_stream:
            element = stream_element.rstrip().split('=')
            if len(element)==2:
                hashed_stream[string.lower(element[0])] = string.lower(element[1])
                
        codec_type = hashed_stream['codec_type']
        try:
            stream_language = hashed_stream['tag:language']
        except KeyError:
            hashed_stream['tag:language'] = config['default_language']
            stream_language = config['default_language']
        if self.include_all_languages:
            if stream_language in self.language_to_exclude[codec_type]:
                log.debug("Ignoring stream %s (%s) in %s" % (command["total_streams"],codec_type,stream_language))
                command["total_streams"] = command["total_streams"]+1
                return command
        else:
            if not stream_language in self.language_to_include[codec_type]:
                log.debug("Ignoring stream %s (%s) in %s" % (command["total_streams"],codec_type,stream_language))
                command["total_streams"] = command["total_streams"]+1
                return command
            
        command["commands"].append("-map")
        command["commands"].append("0:%s" % command["total_streams"])
        
        if codec_type == "video":
            return self.analyze_video_stream(hashed_stream, command, config)
        elif codec_type == "audio":
            return self.analyze_audio_stream(hashed_stream, command, config)
        elif codec_type == "subtitle":
            return self.analyze_subtitles_stream(hashed_stream, command, config)
        
        command["total_streams"] = command["total_streams"]+1
        return command
        
    
    def analyze_video_stream(self,stream,command,config):
        codec = self.codec_options_for_stream(stream, command, config)
        command["commands"].append("-c:v:%s" % command["video_number"])
        command["commands"].extend(codec["codec"].rstrip().split(' '))
        command["video_number"] = command["video_number"]+1
        command["total_streams"] = command["total_streams"]+1
        return command
    
    def analyze_audio_stream(self,stream,command,config):
        codec = self.codec_options_for_stream(stream, command, config)
        command["commands"].append("-c:a:%s" % command["audio_number"])
        command["commands"].extend(codec["codec"].rstrip().split(' '))
        if 'bitrate' in codec:
            command["commands"].append("-b:a:%s" % command["audio_number"])
            command["commands"].append(str(codec['bitrate']))
        if 'channels' in codec:
            command["commands"].append("-ac:%s" % command["audio_number"])
            command["commands"].append(str(codec['channels']))
        command['audio_number'] = command["audio_number"]+1
        command["total_streams"] = command["total_streams"]+1
        
        return command
    
    def analyze_subtitles_stream(self,stream,command,config):
        codec = self.codec_options_for_stream(stream, command, config)
        command["commands"].append("-scodec:%s" % command["subtitle_number"])
        command["commands"].extend(codec["codec"].rstrip().split(' '))
        command["subtitle_number"] = command["subtitle_number"]+1
        command["total_streams"] = command["total_streams"]+1
        return command
        
    def codec_options_for_stream(self,stream,command,config):
        stream_language = stream['tag:language']
        
        # we first check if the stream is in the language specific options
        if "language_specific_options" in config:
            for current_languages_option in config["language_specific_options"]:
                if 'languages_to_include' in current_languages_option:
                    if stream_language in current_languages_option['languages_to_include']:
                        if self.check_requirements_matches_stream(stream, current_languages_option['codec_options']):
                            return current_languages_option['codec_options']
                elif 'languages_to_exclude' in current_languages_option:
                    if not stream_language in current_languages_option['languages_to_exclude']:
                        if self.check_requirements_matches_stream(stream, current_languages_option['codec_options']):
                            return current_languages_option['codec_options']
                    
        # We then check if we have some language independent codec options
        if 'specific_codec_options' in config:
            for current_codec in config['specific_codec_options']:
                if self.check_requirements_matches_stream(stream, current_codec):
                    return current_codec
            
        # No specific configurations found, we use the default one
        if stream['codec_type'] == 'video':
            return config['video_encoding_options']
        elif stream['codec_type'] == 'audio':
            return config['audio_encoding_options']
        elif stream['codec_type'] == 'subtitle':
            return config['subtitles_encoding_options']
        
        return None
        
                
    def check_requirements_matches_stream(self,stream,codec_options):
        codec_type = stream['codec_type']
        if not codec_options['codec_type'] == codec_type:
            return False
        
        # Requirements on original codec
        if 'original_codec_requirements' in codec_options:
            # Original codec name
            if 'original_codec' in codec_options['original_codec_requirements']:
                if 'codec_name' in stream:
                    if not stream['codec_name'] == codec_options['original_codec_requirements']['original_codec']:
                        return False
                else:
                    return False
            # Original codec minimum bitrate
            if 'min_bitrate' in codec_options['original_codec_requirements']:
                if 'bit_rate' in stream:
                    if int(stream['bit_rate']) <= codec_options['original_codec_requirements']['min_bitrate']:
                        return False
                else:
                    return False
            # Original codec maximum bitrate
            if 'max_bitrate' in codec_options['original_codec_requirements']:
                if 'bit_rate' in stream:
                    if int(stream['bit_rate']) >= codec_options['original_codec_requirements']['max_bitrate']:
                        return False
                else:
                    return False
            # Minimum channels
            if 'minimum_channels' in codec_options['original_codec_requirements']:
                if 'channels' in stream:
                    if int(stream['channels']) <= codec_options['original_codec_requirements']['minimum_channels']:
                        return False
                else:
                    return False
            # Maximum channels
            if 'maximum_channels' in codec_options['original_codec_requirements']:
                if 'channels' in stream:
                    if int(stream['channels']) >= codec_options['original_codec_requirements']['maximum_channels']:
                        return False
                else:
                    return False
                
        # Test passed, this codec can be used for this stream
        return True

@event('plugin.register')
def register_plugin():
    plugin.register(FFMPEGEncoder, 'ffmpeg_encoder', api_ver=2)
