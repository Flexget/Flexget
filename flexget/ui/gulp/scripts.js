'use strict';

var path = require('path');
var gulp = require('gulp');

var paths = gulp.paths;

var browserSync = require('browser-sync');

var $ = require('gulp-load-plugins')();

gulp.task('scripts', function () {
  return gulp.src(path.join(paths.src, '/**/*.js'))
    .pipe($.size())
});
