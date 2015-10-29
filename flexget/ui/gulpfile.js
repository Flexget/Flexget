var del = require('del'),
  gulp = require('gulp'),
  mainBowerFiles = require('main-bower-files'),
  uglify = require('gulp-uglify'),
  gutil = require('gulp-util'),
  concat = require('gulp-concat'),
  sourcemaps = require('gulp-sourcemaps'),
  vendor = require('gulp-concat-vendor'),
  flatten = require('gulp-flatten'),
  rename = require('gulp-rename'),
  bower = require('gulp-bower'),
  sass = require('gulp-sass'),
  minifyCSS = require('gulp-minify-css'),
  replace = require('gulp-replace');

var distPath = './vendor',
  config = require('./config.json'),
  bowerDir = './bower_components';

////
// Build JS Files
////
gulp.task('js:clean', function () {
  return del([
    distPath + '/js'
  ]);
});

gulp.task('js', ['js:clean'], function() {
  gulp.src(mainBowerFiles('**/*.js'), { base: bowerDir })
    .pipe(flatten())
    .pipe(sourcemaps.init())
    .pipe(uglify({'preserveComments': 'license'}))
    .pipe(rename({extname: '.min.js'}))
    .pipe(sourcemaps.write('.'))
    .pipe(gulp.dest(distPath + '/js'));

  gulp.src(bowerDir + '/please-wait/build/please-wait.min.js')
    .pipe(rename('splash.min.js'))
    .pipe(gulp.dest(distPath + '/js'));

});


////
// Copy vendor css
////
gulp.task('css:clean', function () {
  return del([
    distPath + '/css'
  ]);
});

gulp.task('css', ['css:clean'], function () {
  gulp.src('./css/vendor/*.scss')
    .pipe(sass({outputStyle: 'compressed'}).on('error', sass.logError))
    // Fix for font paths in angular-ui-grid (does not support sass)
    .pipe(minifyCSS())
    .pipe(rename({extname: '.min.css'}))
    .pipe(replace('../../bower_components/angular-ui-grid', '/ui/vendor/fonts'))
    .pipe(gulp.dest(distPath + '/css'));

  gulp.src(bowerDir + '/please-wait/build/please-wait.css')
    .pipe(rename('splash.css'))
    .pipe(gulp.dest(distPath + '/css'));

});


////
// Build Fonts
////
gulp.task('fonts:clean', function () {
  return del([
    distPath + '/fonts'
  ]);
});

gulp.task('fonts', ['fonts:clean'], function() {
  return gulp.src(config['fonts'])
    .pipe(flatten())
    .pipe(gulp.dest(distPath + '/fonts'));
});


////
// Build All by default
////
gulp.task('default', ['fonts', 'css', 'js']);