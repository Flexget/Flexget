'use strict';

var path = require('path');
var gulp = require('gulp');

var paths = gulp.paths;

var $ = require('gulp-load-plugins')();
var fs = require('fs');

gulp.task('lint', function () {
	var files = gulp.src([
		paths.src + '/**/*.js',
		'!' + paths.src + '/**/*.spec.*']);

	return files
		.pipe($.eslint())
		.pipe($.eslint.format())
		.pipe($.eslint.format('html', fs.createWriteStream('reports/lint.html')))
		.pipe($.eslint.failAfterError());
});
