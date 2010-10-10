import cherrypy

manager = None


class HelloWorld:

    def index(self):
        return "Hello world!"

    index.exposed = True


def start(mg):
    manager = mg

    cherrypy.config.update({
         'server.socket_host': '0.0.0.0',
         'server.socket_port': 5000})

    cherrypy.quickstart(HelloWorld())
