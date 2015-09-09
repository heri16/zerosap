#!python2.7

# http://askubuntu.com/questions/330589/how-to-compile-and-install-dnscrypt
# https://www.digitalocean.com/community/tutorials/how-to-install-zeromq-from-source-on-a-centos-6-x64-vps

import gevent     # gevent.threadpool makes pyrfc yield cooperatively to prevent starvation of zerorpc heartbeats
import pyrfc      # official SAP pyRFC library (require sapnwrfc sdk)
import zerorpc    # high performance rpc library (requires libzmq)
from zerorpc.decorators import rep
from daemonize import Daemonize
from distutils import dir_util
from gevent import queue
import argparse
import hashlib
import logging
import os

# Configuration Variables
RFC_CONN_OPTIONS = {
    'user': os.getenv('ZEROSAP_RFC_USER', 'sap*'),
    'passwd': os.getenv('ZEROSAP_RFC_PASSWD', 'replaceme'),
    'ashost': os.getenv('ZEROSAP_RFC_HOST', '127.0.0.1'),
    'sysnr': os.getenv('ZEROSAP_RFC_SYSNR', '00'),
    'client': os.getenv('ZEROSAP_RFC_CLIENT', '000'),
}

ZMQ_CONN_OPTIONS = {
    'secure': (os.getenv('ZEROSAP_ZMQ_SECURE', '1') != '0'),
    'hub_endpoint': os.getenv('ZEROSAP_ZMQ_HUB', "tcp://localhost:4801"),
    'public_key': os.getenv('ZEROSAP_ZMQ_PUBLIC_KEY', "7f188e5244b02bf497b86de417515cf4d4053ce4eb977aee91a55354655ec33a").decode('hex'),
    'secret_key': os.getenv('ZEROSAP_ZMQ_SECRET_KEY', "1f5d3873472f95e11f4723d858aaf0919ab1fb402cb3097742c606e61dd0d7d8").decode('hex')
}


# System Variables
keep_fds = []
pid = os.getenv('PIDFILE', "/var/run/zerosap.pid")
logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
logger.propagate = False
ch = logging.StreamHandler()
ch.setLevel(logging.INFO)
logger.addHandler(ch)
fh = logging.FileHandler("/var/log/zerosap.log", "w")
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

# Secure Zerorpc Dynamic-Proxy Server Class
class ProxyCurveServer(zerorpc.ProxyServer, zerorpc.CurveServer):
    def __init__(self, *args, **kargs):
        super(ProxyCurveServer, self).__init__(*args, **kargs)
zerorpc.ProxyCurveServer = ProxyCurveServer


# Simple Class to Pool Connections using a Queue
class ConnectionPool(object):
    def __init__(self, max_size, cls, *args, **kargs):
        pool = queue.LifoQueue(max_size)
        self.pool = pool

        class PooledConnection(cls):
            def __exit__(self, *args, **kargs):
                try:
                    pool.put(self, False)
                except queue.Full:
                    return cls.__exit__(self, *args, **kargs)

        self.builder_class = PooledConnection
        self.builder_args = args
        self.builder_kargs = kargs

    def get(self):
        try:
            return self.pool.get(False)
        except queue.Empty:
            return self.builder_class(*self.builder_args, **self.builder_kargs)


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
class RpcToRfcProxy(object):
    #__metaclass__ = RpcMethodsMetaclass

    def __init__(self, zmq_conn_options, rfc_conn_options, rfc_pool_size=16):
        #super(RpcMethods, self).__init__(*args, **kargs)
        self.conn_pool = ConnectionPool(rfc_pool_size, pyrfc.Connection, **rfc_conn_options)
        self.zmq_conn_options = zmq_conn_options

    def __call__(self, method, *args, **kargs):
        params = dict((k,v) for d in args if hasattr(d,'items') for (k,v) in d.items(), **kargs)
        return self.call(method, params)

    def call(self, function_name, function_params):
        log.info("Function Name: {}".format(function_name))
        log.info("Function Params: {}".format(function_params))

        with self.conn_pool.get() as conn:
       	    # Use a gevent.threadpool to prevent heartbeat starvation
            thread_pool = gevent.get_hub().threadpool
            async_result = thread_pool.spawn(conn.call, function_name, **function_params)
            result = async_result.get()

        log.info("Function Result: {}".format(result))
        return result

    def ping(self):
        with self.conn_pool.get() as conn:
            return conn.ping()

    def hello(self, name):
        # return "Hello {}!".format(name)
        requtext = "Hello {}!".format(name).decode('utf-8', 'ignore')
        result = self.call('STFC_CONNECTION', REQUTEXT=requtext)
        log.info(result['ECHOTEXT'])
        return result['ECHOTEXT']

    def download_file(self, endpoint_uri, endpoint_key, command, params, checksum, zmq_secure=True):
        client = zerorpc.CurveClient(timeout=10)
        if zmq_secure:
            client.zmq_socket.curve_secretkey = self.zmq_conn_options['secret_key']
            client.zmq_socket.curve_publickey = self.zmq_conn_options['public_key']
            client.zmq_socket.curve_serverkey = endpoint_key

        log.debug("Connecting to: {}".format(endpoint_uri))
        client.connect(endpoint_uri)

        # Make an outbound connection to endpoint and call streamFile method
        call_args = params    # ['data/filename.xml']
        if not isinstance(call_args, list):
            raise TypeError("call_args must be an array")
        reply = client(command, *call_args)    # Blocks execution

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
    # Test RFC Connection
    try:
        with pyrfc.Connection(**RFC_CONN_OPTIONS) as conn:
            #log.debug(conn.call('STFC_CONNECTION', REQUTEXT=u'Hello SAP!'))
            try:
                conn.ping()
            except pyrfc.RFCError as e:
                log.error('Error: Could not ping the RFC connection')
                log.error(e)
                return
    except pyrfc.LogonError as e:
        log.error('Error: Could not login the RFC connection')
        log.error(e)
        return

    # Setup ZeroRPC Server
    rpc_methods = RpcToRfcProxy(ZMQ_CONN_OPTIONS, RFC_CONN_OPTIONS, rfc_pool_size=8)
    rpc_server = zerorpc.ProxyCurveServer(rpc_methods)
    if ZMQ_CONN_OPTIONS['secure']:
        rpc_server.zmq_socket.curve_server = True
        rpc_server.zmq_socket.curve_secretkey = ZMQ_CONN_OPTIONS['secret_key']
    rpc_server.connect(ZMQ_CONN_OPTIONS['hub_endpoint'])
    log.info("ZeroRPC Server Running...")
    rpc_server.run()


if __name__ == "__main__":
    args = parser.parse_args()
    if args.foreground:
      main()
    else:
      daemon = Daemonize(app="zerosap", pid=pid, action=main, logger=logger, keep_fds=keep_fds, user=os.getenv('USER', "root"), group=os.getenv('GROUP', "sapsys"))
      daemon.start()
