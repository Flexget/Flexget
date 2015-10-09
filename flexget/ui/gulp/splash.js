var del = require('del');
var gulp = require('gulp');
var rename = require('gulp-rename');

var bowerDir = './bower_components';
var wait_package = bowerDir + '/please-wait/build/';

var staticPath = './static';

gulp.task('clean:splash', function () {
  return del([
    staticPath + '/js/splash.min.js',
    staticPath + '/css/splash.min.js'
  ]);
});


gulp.task('splash', ['clean:splash'], function() {
  gulp.src(wait_package + 'please-wait.css')
    .pipe(rename('splash.css'))
    .pipe(gulp.dest(staticPath + '/css'));

  gulp.src(wait_package + 'please-wait.min.js')
    .pipe(rename('splash.min.js'))
    .pipe(gulp.dest(staticPath + '/js'));

});