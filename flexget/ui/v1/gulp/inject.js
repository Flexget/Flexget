'use strict';

var gulp = require('gulp');

var paths = gulp.paths;

var $ = require('gulp-load-plugins')();

var wiredep = require('wiredep').stream;


gulp.task('inject', ['styles'], function () {

  var injectStyles = gulp.src(paths.tmp + '/serve/**/*.css', { read: false });
  var injectScripts = gulp.src([
    paths.src + '/**/*.js',
    '!' + paths.src + '/app.module.js',
	'!' + paths.src + '/app.utils.js',
    '!' + paths.src + '/app.loading.js',
    '!' + paths.src + '/**/*.spec.js'
  ]).pipe($.angularFilesort()).pipe($.angularFilesort());

  var injectOptions = {
    ignorePath: [paths.src, paths.tmp + '/serve'],
    addRootSlash: false
  };

  var wiredepOptions = {
    directory: 'bower_components',
    ignorePath: '../',
    exclude: [/angular-material\.css/]
  };

  return gulp.src(paths.src + '/app.html')
    .pipe($.inject(injectStyles, injectOptions))
    .pipe($.inject(injectScripts, injectOptions))
    .pipe(wiredep(wiredepOptions))
    .pipe(gulp.dest(paths.tmp + '/serve'));

});
