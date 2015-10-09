var del = require('del');
var sass = require('gulp-sass');
var urlAdjuster = require('gulp-css-url-adjuster');
var gulp = require('gulp');
var minifyCSS = require('gulp-minify-css');
var sourcemaps = require('gulp-sourcemaps');
var rename = require('gulp-rename');

var staticPath = './static';
var config = require('../ui.json');

gulp.task('clean:css', function () {
  return del([
    staticPath + '/css/flexget.min.css',
    staticPath + '/css/flexget.min.map'
  ]);
});


gulp.task('css',['clean:css'], function () {
  gulp.src('./sass/flexget.scss')
    .pipe(sass({includePaths: config.sass_includes, outputStyle: 'compressed'}).on('error', sass.logError))
    // Fix for font paths in angular-ui-grid (does not support sass)
    .pipe(urlAdjuster({
      prependRelative: '../fonts/',
      append: '?version=1'
    }))
    .pipe(sourcemaps.init())
    .pipe(minifyCSS())
    .pipe(rename('flexget.min.css'))
    .pipe(sourcemaps.write('.'))
    .pipe(gulp.dest(staticPath + '/css'));
});


gulp.task('watch:css', function() {
  gulp.watch('./sass/**/*.scss', ['css']);
});
