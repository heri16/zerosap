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
var keys = require('./keys');

/* Patch ZeroRPC API to add features such as encryption */
require('./patches').zerorpc(zerorpc);

/* System variables */
var sapClientPool = {};

/* Config variables */
var rpcSidPorts = {
  // To allow streamFile downloads, open secondary ports that are 100 above each of the ports listed here...
  DEV: 4803,
  PRD: 4801
};

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
function SapClient(sid, host, port, zmqPublicKey, zmqSecretKey) {
  SapClient.super_.apply(this, Array.prototype.slice.call(arguments, 4));

  // Make client secure
  this.zmqPublicKey = zmqPublicKey;
  this.curveEnable(zmqSecretKey, zmqPublicKey);
  this.curveServerKey( keys.lookupSidKey(sid) );

  // Make client wait for inbound connection
  this.clientHost = host;
  this.clientPort = port;
  this.bind('tcp://0.0.0.0:' + this.clientPort);

  // Create Callback RPC Server that is called by remote-end
  this.server = new zerorpc.Server(rpcCbMethods);
  this.server.curveEnable(zmqSecretKey);
  this.serverHost = this.clientHost;
  this.serverPort = this.clientPort + 100;
  this.serverState = 0;
  //this.server.bind('tcp://0.0.0.0:' + this.serverPort);
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
      self.invoke('download_file', 'tcp://' + self.serverHost + ':' + self.serverPort, self.zmqPublicKey, 'streamFile', [fsPath], checksum, function(err, res, more) {
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
exports.getSapClient = function(sid, host, port, zmqPublicKey, zmqPrivateKey) {
  if(!host) { host = os.hostname(); }
  if(!port) { port = rpcSidPorts[sid]; }
  if(!zmqPublicKey) { zmqPublicKey = new Buffer('ea1cc8bd7c8af65497d43fc21dbec6560c5e7b61bcfdcbd2b0dfacf0b4c38d45', 'hex'); }
  if(!zmqPrivateKey) { zmqPrivateKey = new Buffer('83f99afacfab052406e5f421612568034e85f4c8182a1c92671e83dca669d31d', 'hex'); }

  var sapClient = sapClientPool[sid];
  if (!sapClient) {
    if (!host || !port) { return null; }
    sapClient = new SapClient(sid, host, port, zmqPublicKey, zmqPrivateKey);
    sapClientPool[sid] = sapClient;
  }
  return sapClient;
};
