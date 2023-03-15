'use strict';

var gulp = require('gulp');

var paths = gulp.paths;

var browserSync = require('browser-sync');

var middleware = require('./proxy');

function browserSyncInit(baseDir, files, browser) {
    browser = browser ? 'default' : browser;

    var routes = {
        '/bower_components': 'bower_components'
    };

    browserSync.instance = browserSync.init(files, {
        startPath: '/',
        index: 'app.html',
        server: {
            baseDir: baseDir,
            middleware: middleware,
            routes: routes
        },
        port: 3000,
        browser: browser
    });
}

gulp.task('serve', ['watch'], function () {
    browserSyncInit([
        paths.tmp + '/serve',
        paths.src
    ], [
        paths.tmp + '/serve/**/*.css',
        paths.src + '/**/*.js',
        paths.src + 'src/assets/images/**/*',
        paths.tmp + '/serve/*.html',
        paths.tmp + '/serve/app/**/*.html',
        paths.src + '/**/*.html'
    ]);
});