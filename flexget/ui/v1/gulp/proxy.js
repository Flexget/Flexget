/* eslint-disable no-console */
'use strict';

var httpProxy = require('http-proxy');
var chalk = require('chalk');
var util = require('gulp-util');

var proxyTarget = 'http://' + (util.env.server ? util.env.server : '127.0.0.1:5050') + '/';

var proxy = httpProxy.createProxyServer({
    target: proxyTarget
});

proxy.on('error', function (error, req, res) {
    res.writeHead(500, {
        'Content-Type': 'text/plain'
    });

    console.error(chalk.red('[Proxy]'), error);
});

function proxyMiddleware(req, res, next) {
    if (req.url === '/') {
        next();
    } else if (/^\/api\//.test(req.url)) {
        proxy.web(req, res);
    } else {
        next();
    }
}

module.exports = [proxyMiddleware];
