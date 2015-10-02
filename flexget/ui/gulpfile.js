'use strict';

var gulp = require('gulp');
var sass = require('gulp-sass');
var notify = require("gulp-notify");
var bower = require('gulp-bower');
var vendor = require('gulp-concat-vendor');
var mainBowerFiles = require('main-bower-files');
var uglify = require('gulp-uglify');
var clean = require('gulp-clean');
var gutil = require('gulp-util');
var concat = require('gulp-concat');
var flatten = require('gulp-flatten');
var urlAdjuster = require('gulp-css-url-adjuster');
var sourcemaps = require('gulp-sourcemaps');

var config = require('./ui.json');

var bowerDir = './bower_components';
var staticPath = './static';

gulp.task('bower', function() {
  return bower()
    .pipe(gulp.dest(bowerDir))
});

gulp.task('clean', function () {
  var paths = [
    staticPath + '/js',
    staticPath + '/css',
    staticPath + '/fonts'
  ];
  return gulp.src(paths, {read: false})
    .pipe(clean());
});


gulp.task('fonts', function() {
  return gulp.src(config.fonts)
    .pipe(flatten())
    .pipe(gulp.dest(staticPath + '/fonts'));
});


gulp.task('css', function () {
  gulp.src('./sass/flexget.scss')
    .pipe(sass({includePaths: config.sass_includes, outputStyle: 'compressed'}).on('error', sass.logError))
    // Fix for angular-ui-grid fonts (does not support sassat
    .pipe(urlAdjuster({
      prependRelative: '../fonts/',
      append: '?version=1',
    }))
    .pipe(gulp.dest(staticPath + '/css'));
});


gulp.task('vendor-js', function() {
  return gulp.src(mainBowerFiles('**/*.js'), { base: bowerDir })
    .pipe(vendor('vendor.min.js'))
    .pipe(uglify().on('error', gutil.log))
    .pipe(gulp.dest(staticPath + '/js'))
});

gulp.task('flexget-js', function() {
  return gulp.src(config.js)
    .pipe(sourcemaps.init())
    .pipe(concat('flexget.min.js'))
    .pipe(uglify({ mangle: false }).on('error', gutil.log))
    .pipe(sourcemaps.write('.'))
    .pipe(gulp.dest(staticPath + '/js/'));
});

gulp.task('watch', function() {
  gulp.watch(config.js, ['flexget-js']);
});

gulp.task('default', ['bower', 'fonts', 'css', 'vendor-js', 'flexget-js']);