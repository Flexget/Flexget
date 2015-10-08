var del = require('del');
var gulp = require('gulp');
var mainBowerFiles = require('main-bower-files');
var uglify = require('gulp-uglify');
var gutil = require('gulp-util');
var concat = require('gulp-concat');
var sourcemaps = require('gulp-sourcemaps');
var vendor = require('gulp-concat-vendor');

var staticPath = './static';
var config = require('../ui.json');
var bowerDir = './bower_components';


gulp.task('clean:js:vendor', function () {
  return del([
    staticPath + '/js'
  ]);
});

gulp.task('clean:js:flexget', function () {
  return del([
    staticPath + '/js'
  ]);
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

gulp.task('js', ['flexget-js', 'vendor-js'], function() {
  gulp.watch(config.js, ['flexget-js']);
});


gulp.task('watch:js', function() {
  gulp.watch(config.js, ['flexget-js']);
});
