import logging
import telnetlib
from flexget.plugin import register_plugin

log = logging.getLogger('mldonkey')


class OutputMlDonkey(object):
    """
    Example::

      mldonkey:
        ip: localhost
        port: 4000
        timeout: 60
        priority: 0
        top: False
    """

    schema = {
        'type': 'object',
        'properties': {
            'ip': {'type': 'string', 'default': 'localhost'},
            'port': {'type': 'integer', 'default': 4000},
            'timeout': {'type': 'integer','default': 60},
            'user': {'type': 'string', 'default': 'admin'},
            'pwd': {'type': 'string' }
        },
        'required': ['pwd'],
        'additionalProperties': False
    }

    def on_task_output(self, task, config):
        from xmlrpclib import ServerProxy

        params = dict(config)

        tn = telnetlib.Telnet()

	try:
	    tn.open(params['ip'],params['port'],params['timeout'])
	except IOError:
	    log.error("Timeout after %s sec or other IO problem" % timeout)
	    sys.exit()
	else:
            try:
	        tn.read_until("MLdonkey command-line:")

                tn.write(b"auth " + params['user'].encode('ascii') + b" " + params['pwd'].encode('ascii') + b"\r\n")

                tn.read_until("MLdonkey command-line:")
            except EOFError:
                log.error('Receive EOF to soon')
		sys.exit()
	    except:
	        log.error('An unknow error/exception occured')
	    else:

                for entry in task.accepted:
                    if task.manager.options.test:
                        log.info('Would add into mldonkey: %s' % entry['url'])
                        continue
    
                    try:
                        tn.write(b"dllink " + entry['url'].encode('ascii') + b"\r\n")
                        tn.read_until("MLdonkey command-line:")
                        log.info("Added `%s` to mldonkey" % entry["url"])
                    except:
                        log.critical("Could not add link to mldonkey : %s" % entry['url'])
                        entry.fail("could not call appendurl via RPC")

                tn.write(b"quit\r\n")

register_plugin(OutputMlDonkey, 'mldonkey', api_ver=2)
