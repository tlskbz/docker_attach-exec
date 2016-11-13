"""Flasknado! - A simple example of using Flask and Tornado
together.

"""

from __future__ import print_function
from flask import Flask, render_template
import tornado
from tornado.wsgi import WSGIContainer
from tornado.web import Application, FallbackHandler
from tornado.websocket import WebSocketHandler
from tornado.ioloop import IOLoop

ssl_option = {'keyfile': '~/key.pem',
              'certfile': '~/cert.pem'}


class StatsSock(WebSocketHandler):
    def __init__(self, application, request, **kwargs):
        WebSocketHandler.__init__(self, application, request, **kwargs)

    @tornado.gen.coroutine
    def open(self):
        host = '192.168.1.13'
        port = 2375

        @tornado.gen.coroutine
        def cab(msg):
            try:
                self.write_message(msg)
            except Exception, e:
                pass

        try:
            http = tornado.httpclient.AsyncHTTPClient()
            yield http.fetch(tornado.httpclient.HTTPRequest(
                "http://192.168.1.13:2375/containers/62189d56592ddc1403ce1cccf31ee9ac61c64e2624469bf6c049f85e26fe4755/stats?stream=1",
                streaming_callback=cab, request_timeout=60.0))
        except Exception, e:
            self.close()

    def on_close(self):
        pass

    @tornado.gen.coroutine
    def on_message(self, message):
        pass

    def check_origin(self, origin):
        return True


app = Flask('flasknado')


@app.route('/')
def index():
    return render_template('index.html')


if __name__ == "__main__":
    container = WSGIContainer(app)
    server = Application([
        (r'/stats', StatsSock),
        (r'.*', FallbackHandler, dict(fallback=container))
    ])
    server.listen(8013)
    IOLoop.instance().start()
