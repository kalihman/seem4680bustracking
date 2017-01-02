var EBS = require('eddystone-beacon-scanner');
var http = require('http');
var request = require('request');
var inspect = require('eyespect').inspector();

function sendSignal(data) {
    var body = JSON.stringify(data);
    var options = {
        url: "http://52.221.223.238/scanner",
        method: "POST",
        headers: {
            "Content-Type": "application/json",
            "Cache-Control": "no-cache",
            "Content-Length": Buffer.byteLength(body)
        },
        json: true,
        body: data
    };
    request(options, function(err, res, body) {
        if(err) {
            inspect(err, 'error posting');
            return
        }
        var headers = res.headers
        var status = res.statusCode
        inspect(headers, 'headers')
        inspect(status, 'status')
        inspect(body, 'body')
    });
}
function dataHandler(data, status) {
    data['status'] = status;
    data['station'] = 'main_campus' 
    //data['lastSeen'] = (new Date(data['lastSeen'])).toString();
    return data;
}

EBS.on('found', function(beacon) {
    beacon = dataHandler(beacon, 'found');
    console.log('found Eddystone Beacon:\n', JSON.stringify(beacon,null,2));
    sendSignal(beacon);
});

EBS.on('updated', function(beacon) {
    //console.log('updated Eddyston Beacon:\n', JSON.stringify(beacon,null,2));
    //sendSignal(beacon);
});
EBS.on('lost', function(beacon) {
    beacon = dataHandler(beacon, 'lost');
    console.log('lost Eddystone Beacon:\n', JSON.stringify(beacon,null,2));
    sendSignal(beacon);
});

EBS.startScanning(true);
