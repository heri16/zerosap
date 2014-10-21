var fs = require('fs');
var crypto = require('crypto');

/* Function to calculate SHA1 of a file */
exports.digestFileSHA1 = function(filePath, cb) {
    var hash = crypto.createHash('sha1');
    var stream = fs.createReadStream(filePath);

    stream.on('data', function(chunk) { hash.update(chunk); });
    stream.on('end', function() { cb(null, hash.digest('hex')); });
};
