/*
 * http://askubuntu.com/questions/330589/how-to-compile-and-install-dnscrypt
 * https://www.digitalocean.com/community/tutorials/how-to-install-zeromq-from-source-on-a-centos-6-x64-vps
 */

/* Libraries */
var zerorpc = require('zerorpc');
var async = require('async');

var util = require('util');
var fs = require('fs');
var os = require('os');

var helpers = require('./helpers');

/* Patch ZeroRPC API to add features such as encryption */
require('./patches').zerorpc(zerorpc);

/* System variables */
var sapClientPool = {};

/* Callback RPC Methods used for streaming files */
var rpcCbMethods = {
  streamFile: function(path, range) {
    var reply = arguments[arguments.length - 1];

    console.log('streamFile: ' + path);

    var readable = fs.createReadStream(path);
    readable.on('data', function(chunk) {
      //console.log('got %d bytes of data', chunk.length);
      reply(null, chunk, true)
    });
    readable.on('end', function() {
      reply();
    });
    readable.on('error', function(err) {
      console.log(err);
      reply(err);
    });

  }
};

/* Subclass ZeroRPC Client */
function SapClient(options) {
  SapClient.super_.apply(this, options);

  // Default values
  options = options || {};
  var clientPort = options.port || 4801;
  var callbackUri = options.callbackUri || ('tcp://127.0.0.1:' + (clientPort + 100) );

  var zmqSecure = options.secure || true;
  var zmqServerKey = options.serverKey || new Buffer('7f188e5244b02bf497b86de417515cf4d4053ce4eb977aee91a55354655ec33a', 'hex');
  var zmqPublicKey = options.publicKey || new Buffer('ea1cc8bd7c8af65497d43fc21dbec6560c5e7b61bcfdcbd2b0dfacf0b4c38d45', 'hex');
  var zmqSecretKey = options.secretKey || new Buffer('83f99afacfab052406e5f421612568034e85f4c8182a1c92671e83dca669d31d', 'hex');

  // Make client secure
  if (zmqSecure) {
    this.zmqPublicKey = zmqPublicKey;
    this.curveEnable(zmqSecretKey, zmqPublicKey);
    this.curveServerKey(zmqServerKey);
  }

  // Make client wait for inbound connection
  this.clientPort = clientPort;
  this.bind('tcp://0.0.0.0:' + this.clientPort);

  if (callbackUri) {
    // Create Callback RPC Server that is called by remote-end
    this.callbackUri = callbackUri;
    this.server = new zerorpc.Server(rpcCbMethods);
    this.server.curveEnable(zmqSecretKey);
    this.serverPort = +this.callbackUri.substring(this.callbackUri.lastIndexOf(':') + 1);
    this.serverState = 0;
    //this.server.bind('tcp://0.0.0.0:' + this.serverPort);
  }
}
util.inherits(SapClient, zerorpc.Client);

SapClient.prototype.call = function(funcName, funcParams, cb) {
  this.invoke('call', funcName, funcParams, cb);
};

SapClient.prototype.uploadFile = function(fsPath, cb) {
  var self = this;

  fs.stat(fsPath, function(err, stats) {
    if (err) { cb(err); return; }
    if (!stats.isFile()) { cb(new Error("fsPath does not lead to  a file")); return; } 

    // Calculate checksum
    helpers.digestFileSHA1(fsPath, function(err, checksum) {
      if (err) { cb(err); return; }

      // Enable server to listen to port
      //try {
        // Bind only if not binded
        if (0 === self.serverState++) {
          //console.log('Server Binding');
          self.server.bind('tcp://0.0.0.0:' + self.serverPort);
        }
      //} catch(ex) {}

      // Call the remote download_file procedure
      self.invoke('download_file', self.callbackUri, self.zmqPublicKey, 'streamFile', [fsPath], checksum, function(err, res, more) {
        // Make the server stop listening on the port
        process.nextTick(function() {
          //setImmediate(function() {
            //try {
              if (0 === --self.serverState) {
                //console.log('Server Unbinding');
                self.server.unbind('tcp://0.0.0.0:' + self.serverPort);
              }
            //} catch(ex) {}
          //});
        });

        cb(err, res);
      });

    });
  });
};

SapClient.prototype.uploadFiles = function(fsPaths, cb) {
  var self = this;

  if (!Array.isArray(fsPaths)) {
    cb(new Error("fsPaths is not an array"));
    return;
  }
  
  // Upload each file in parallel
  async.mapLimit(fsPaths, 5, self.uploadFile.bind(self), cb);
};

exports.SapClient = SapClient;

/* Get SapClient from Pool, or help generate a new one */
exports.getSapClient = function(sid, options) {
  var sapClient = sapClientPool[sid];
  if (!sapClient) {
    sapClient = new SapClient(options);
    sapClient.sid = sid;
    sapClientPool[sid] = sapClient;
  }
  return sapClient;
};
