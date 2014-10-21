var zerosap = require('./index');

var sapClient = zerosap.getSapClient('DEV', '10.0.1.230', 4242);
sapClient.invoke('ping', function(err, res) {
  if (err) return console.log(err);
  console.log('RFC Server responded to ping.');
  
  sapClient.uploadFiles(['data/import.xml', 'data/A.xml', 'data/B.xml', 'data/A.xml', 'data/B.xml', 'data/A.xml', 'data/B.xml', 'data/A.xml', 'data/B.xml'], function(err, res) {
     if (err) return console.log(err);
     console.log('uploadFile: ' + res);

     sapClient.invoke('STFC_CONNECTION', {REQUTEXT: "Hello SAP"}, function(err, res) {
       if (err) return console.log(err);
       console.log(res['ECHOTEXT']);
     });
  });
});
