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
import json

ssl_option = {'keyfile': '~/key.pem',
              'certfile': '~/cert.pem'}


class AttachSock(WebSocketHandler):
    def __init__(self, application, request, **kwargs):
        WebSocketHandler.__init__(self, application, request, **kwargs)

    @tornado.gen.coroutine
    def open(self):
        id = (self.get_argument('id', None))
        host = ''
        port = 2376

        tcp_client = tornado.tcpclient.TCPClient()
        conn = yield tcp_client.connect(host, port, ssl_options=ssl_option)

        yield conn.write(
            b'POST /containers/{}/attach?logs=1&stdin=1&stderr=1&stdout=1&stream=1 HTTP/1.1\r\n'.format(id))
        yield conn.write(b'Host: {}:{}\r\n'.format(host, port))
        yield conn.write(b'Connection: Upgrade\r\n')
        yield conn.write(b'Upgrade: tcp\r\n')
        yield conn.write(b"\r\n")
        res = yield conn.read_until(b'\r\n\r\n')
        self.termin_conn = conn

        @tornado.gen.coroutine
        def test():
            while True:
                try:
                    data = yield conn.read_bytes(1024, partial=True)
                    self.write_message(data)
                except Exception, e:
                    self.termin_conn.close()
                    print(e)
                    break

        yield test()

    def on_close(self):
        try:
            self.termin_conn.close()
        except Exception, e:
            pass

    @tornado.gen.coroutine
    def on_message(self, message):
        pass

    def check_origin(self, origin):
        return True


class ExecSock(WebSocketHandler):
    def __init__(self, application, request, **kwargs):
        WebSocketHandler.__init__(self, application, request, **kwargs)

    @tornado.gen.coroutine
    def open(self):
        id = (self.get_argument('id', None))
        host = ''
        port = 2376

        tcp_client = tornado.tcpclient.TCPClient()
        conn = yield tcp_client.connect(host, port, ssl_options=ssl_option)

        body = json.dumps({
            'AttachStdin': True,
            'AttachStdout': True,
            'AttachStderr': True,
            'DetachKeys': 'ctrl-p,ctrl-q',
            'Tty': True,
            'Cmd': [
                '/bin/bash'
            ]
        })
        yield conn.write(b'POST /containers/{}/exec HTTP/1.1\r\n'.format(id) +
                         b'Host: {}:{}\r\n'.format(host, port) +
                         b'Content-Type: application/json\r\n' +
                         b'Content-Length: {}\r\n'.format(len(body)) +
                         b"\r\n" +
                         body.encode('utf-8'))
        res = yield conn.read_until(b'\r\n\r\n')
        data = yield conn.read_bytes(1024, partial=True)

        exec_id = json.loads(data)['Id']

        data = json.dumps({
            'Detach': False,
            'Tty': True
        })
        yield conn.write(b'POST /exec/{}/start HTTP/1.1\r\n'.format(exec_id))
        yield conn.write(b'Host: {}:{}\r\n'.format(host, port))
        yield conn.write(b'Connection: Upgrade\r\n')
        yield conn.write(b'Content-Type: application/json\r\n')
        yield conn.write(b'Upgrade: tcp\r\n')
        yield conn.write(b'Content-Length: {}\r\n'.format(len(data)))
        yield conn.write(b"\r\n")
        yield conn.write(data.encode('utf-8'))
        res = yield conn.read_until(b'\r\n\r\n')

        self.termin_conn = conn

        @tornado.gen.coroutine
        def test():
            while True:
                try:
                    data = yield conn.read_bytes(1024, partial=True)
                    self.write_message(data)
                except tornado.iostream.StreamClosedError:
                    print("error on server")
                    self.close()
                    break

        yield test()

    @tornado.gen.coroutine
    def on_message(self, message):
        try:
            yield self.termin_conn.write(message.encode('utf-8'))
        except tornado.iostream.StreamClosedError:
            self.write_message('Terminal has disconnected.')
            self.close()

    def on_close(self):
        try:
            self.termin_conn.write('\nexit\n')
            self.termin_conn.close()
        except tornado.iostream.StreamClosedError:
            pass

    def check_origin(self, origin):
        return True


app = Flask('flasknado')


@app.route('/')
def index():
    return render_template('exec.html')


if __name__ == "__main__":
    container = WSGIContainer(app)
    server = Application([
        (r'/exec/', ExecSock),
        (r'/attach/', AttachSock),
        (r'.*', FallbackHandler, dict(fallback=container))
    ])
    server.listen(8013)
    IOLoop.instance().start()
