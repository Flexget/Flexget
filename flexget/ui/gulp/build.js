var bower = require('gulp-bower');
var gulp = require('gulp');

var bowerDir = './bower_components';


gulp.task('bower', function() {
  return bower()
    .pipe(gulp.dest(bowerDir))
});


gulp.task('default', ['bower', 'fonts', 'css', 'js']);