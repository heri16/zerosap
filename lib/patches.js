exports.zerorpc = function(zerorpc) {

/* Patch to expose Server socket */
zerorpc.Server.prototype.zmqSocket = function() {
    return this._socket._zmqSocket;
};
/* Patch to expose Client socket */
zerorpc.Client.prototype.zmqSocket = function() {
    return this._socket._zmqSocket;
};
/* Patch to enable Server socket unbind */
zerorpc.Server.prototype.unbind = function(endpoint) {
    this.zmqSocket().unbindSync(endpoint);
};
/* Patch to enable Server CURVE encryption */
zerorpc.Server.prototype.curveEnable = function(serverPrivateKey) {
    var rep = this.zmqSocket();
    rep.curve_server = 1;
    rep.curve_secretkey = serverPrivateKey;
};
/* Patch to enable Client CURVE encryption */
zerorpc.Client.prototype.curveEnable = function(clientPrivateKey, clientPublicKey) {
    var req = this.zmqSocket();
    req.curve_secretkey = clientPrivateKey;
    req.curve_publickey = clientPublicKey;
};
zerorpc.Client.prototype.curveServerKey = function(serverPublicKey) {
    var req = this.zmqSocket();
    if (serverPublicKey) { req.curve_serverkey = serverPublicKey; }
    else { return req.curve_serverkey; }
};

}
