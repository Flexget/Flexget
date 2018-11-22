from flexget import plugin

try:
    import transmissionrpc
    from transmissionrpc import TransmissionError
    from transmissionrpc import HTTPHandlerError
except ImportError:
    # If transmissionrpc is not found, errors will be shown later
    pass


def create_rpc_client(config):
    user, password = config.get('username'), config.get('password')

    try:
        return transmissionrpc.Client(config['host'], config['port'], user, password)
    except TransmissionError as e:
        if isinstance(e.original, HTTPHandlerError):
            if e.original.code == 111:
                raise plugin.PluginError("Cannot connect to transmission. Is it running?")
            elif e.original.code == 401:
                raise plugin.PluginError("Username/password for transmission is incorrect. Cannot connect.")
            elif e.original.code == 110:
                raise plugin.PluginError("Cannot connect to transmission: Connection timed out.")
            else:
                raise plugin.PluginError("Error connecting to transmission: %s" % e.original.message)
        else:
            raise plugin.PluginError("Error connecting to transmission: %s" % e.message)
