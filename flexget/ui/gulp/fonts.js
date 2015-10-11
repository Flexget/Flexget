var del = require('del');
var gulp = require('gulp');
var flatten = require('gulp-flatten');

var staticPath = './static';
var config = require('../ui.json');

gulp.task('clean:fonts', function () {
  return del([
    staticPath + '/fonts'
  ]);
});


gulp.task('fonts', ['clean:fonts'], function() {
  return gulp.src(config.fonts)
    .pipe(flatten())
    .pipe(gulp.dest(staticPath + '/fonts'));
});
