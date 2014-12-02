#!python2.7

# http://askubuntu.com/questions/330589/how-to-compile-and-install-dnscrypt
# https://www.digitalocean.com/community/tutorials/how-to-install-zeromq-from-source-on-a-centos-6-x64-vps

import zerorpc
from zerorpc.decorators import rep
import pyrfc
from daemonize import Daemonize
from distutils import dir_util
import argparse
import hashlib
import logging
import os

# Config-defined Variables
rfc_conn_params = {
    'user': os.getenv('ZEROSAP_RFC_USER', 'sap*'),
    'passwd': os.getenv('ZEROSAP_RFC_PASSWD', 'replaceme'),
    'ashost': os.getenv('ZEROSAP_RFC_HOST', '127.0.0.1'),
    'sysnr': os.getenv('ZEROSAP_RFC_SYSNR', '00'),
    'client': os.getenv('ZEROSAP_RFC_CLIENT', '000')
}
zmq_client_endpoint = os.getenv('ZEROSAP_CLIENT', "tcp://10.1.1.100:4242")
zmq_public_key = os.getenv('ZEROSAP_ZMQ_PUB_KEY', "7f188e5244b02bf497b86de417515cf4d4053ce4eb977aee91a55354655ec33a").decode('hex')
zmq_private_key = os.getenv('ZEROSAP_ZMQ_PRV_KEY', "1f5d3873472f95e11f4723d858aaf0919ab1fb402cb3097742c606e61dd0d7d8").decode('hex')


# System Variables
keep_fds = []
pid = "/tmp/zerosap.pid"
logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
logger.propagate = False
ch = logging.StreamHandler()
ch.setLevel(logging.INFO)
logger.addHandler(ch)
fh = logging.FileHandler("/tmp/zerosap.log", "w")
keep_fds.append(fh.stream.fileno())
fh.setLevel(logging.DEBUG)
logger.addHandler(fh)
log = logger

# Declare Arguments
parser = argparse.ArgumentParser()
parser.add_argument('-f', '--foreground', help="keep in foreground. do not run in daemon mode", action='store_true')

# A custom implementation of collections.defaultdict
class Defaultdict(dict):
    def __init__(self, factory, mapping, **kwarg):
        dict.__init__(self, mapping, **kwarg)
        self.factory = factory
    def __missing__(self, key):
        self[key] = self.factory(key)
        return self[key]
    def get(self, key, defaultVal):
        return self[key]

# Patch Zerorpc Server to expose zmq socket
class CurveServer(zerorpc.Server):
    @property
    def zmq_socket(self):
        return self._events._socket
zerorpc.CurveServer = CurveServer

# Patch Zerorpc Client to expose zmq socket
class CurveClient(zerorpc.Client):
    @property
    def zmq_socket(self):
        return self._events._socket
zerorpc.CurveClient = CurveClient

# Subclass Zerorpc Server to enable Dynamic Proxy using __call__() or call()
class ProxyServer(zerorpc.Server):
    def __init__(self, methods=None, *args, **kargs):
        super(ProxyServer, self).__init__(methods, *args, **kargs)
        self._methods_call = methods.__call__ if hasattr(methods, '__call__') else methods.call if hasattr(methods, 'call') else None
        if self._methods_call:
            self._methods = Defaultdict((lambda key: rep(lambda *args, **kargs: self._methods_call(key, *args, **kargs))), self._methods)
zerorpc.ProxyServer = ProxyServer
class ProxyCurveServer(zerorpc.ProxyServer, zerorpc.CurveServer):
    def __init__(self, *args, **kargs):
        super(ProxyCurveServer, self).__init__(*args, **kargs)
zerorpc.ProxyCurveServer = ProxyCurveServer


# Function to calculate SHA1 of a file
def digest_file_sha1(file_path):
    BLOCKSIZE = 65536
    hasher = hashlib.sha1()
    with open(file_path, 'rb') as afile:
        buf = afile.read(BLOCKSIZE)
        while len(buf) > 0:
            hasher.update(buf)
            buf = afile.read(BLOCKSIZE)
    return hasher.hexdigest()


# Class containing exposed RPC Methods
class RpcMethods(object):
    #__metaclass__ = RpcMethodsMetaclass

    def __init__(self, conn, *args, **kargs):
        #super(RpcMethods, self).__init__(*args, **kargs)
        self.conn = conn

    def __call__(self, method, *args, **kargs):
        params = dict((k,v) for d in args if hasattr(d,'items') for (k,v) in d.items(), **kargs)
        return self.call(method, params)

    def call(self, function_name, function_params):
        log.info("Function Name: {}".format(function_name))
        log.info("Function Params: {}".format(function_params))
        response = self.conn.call(function_name, **function_params)
        log.info("Function Response: {}".format(response))
        return response

    def ping(self):
        return self.conn.ping()

    def hello(self, name):
        # return "Hello {}!".format(name)
        requtext = "Hello {}!".format(name).decode('utf-8', 'ignore')
        result = conn.call('STFC_CONNECTION', REQUTEXT=requtext)
        log.info(result['ECHOTEXT'])
        return result['ECHOTEXT']

    def download_file(self, endpoint, endpointKey, command, params, checksum):
        client = zerorpc.CurveClient(timeout=10)
        client.zmq_socket.curve_secretkey = zmq_private_key
        client.zmq_socket.curve_publickey = zmq_public_key

        log.debug("Connecting to: {}".format(endpoint))
        client.zmq_socket.curve_serverkey = endpointKey
        client.connect(endpoint)

        # Make an outbound connection to endpoint and call streamFile method
        call_args = params  # ['data/import.xml']
        if not isinstance(call_args, list):
            raise TypeError("call_args must be an array")
        reply = client(command, *call_args)  # Blocks execution

        # Write the reply out to filesystem
        r_fpath = params[0]
        dir_util.create_tree('/tmp/', [r_fpath], mode=511)
        fpath = '/tmp/' + r_fpath
        with open(fpath, 'wb') as f:
            for chunk in reply:
                f.write(chunk)

        # Ensure integrity of file
        digest = digest_file_sha1(fpath)
        if digest != checksum:
            log.info("Download BAD-Checksum: {}".format(fpath))
            return "BAD"
        else:
            log.info("Download OK: {}".format(fpath))
            return "OK"


def main():
    with pyrfc.Connection(**rfc_conn_params) as conn:
        result = conn.call('STFC_CONNECTION', REQUTEXT=u'Hello SAP!')
        log.debug(result)

        server = zerorpc.ProxyCurveServer(RpcMethods(conn))
        server.zmq_socket.curve_server = True
        server.zmq_socket.curve_secretkey = zmq_private_key
        server.connect(zmq_client_endpoint)
        log.info("Running...")
        server.run()


if __name__ == "__main__":
    args = parser.parse_args()
    if args.foreground:
      main()
    else:
      daemon = Daemonize(app="zerosap", pid=pid, action=main, logger=logger, keep_fds=keep_fds, user=os.getenv('USER', "root"), group=os.getenv('GROUP', "sapsys"))
      daemon.start()
