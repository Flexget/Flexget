'use strict';

var gulp = require('gulp');

gulp.paths = {
  src: 'src',
  dist: 'app',
  tmp: '.tmp',
  specs: '.',
  spechelpers: 'tests-mock-data'
};

require('require-dir')('./gulp');

gulp.task('build', ['clean'], function () {
    gulp.start('buildapp');
});

gulp.task('default', ['build']);