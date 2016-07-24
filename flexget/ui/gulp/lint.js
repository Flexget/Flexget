'use strict';

var gulp = require('gulp');

var paths = gulp.paths;

var $ = require('gulp-load-plugins')();
var fs = require('fs');

function isFixed(file) {
	return file.eslint != null && file.eslint.fixed;
}

gulp.task('lint', function () {
	var files = gulp.src([
		paths.src + '/**/*.js',
		'!' + paths.src + '/**/*.spec.*']);

	return files
		.pipe($.eslint({
			fix: true
		}))
		.pipe($.eslint.format())
		.pipe($.eslint.format('html', fs.createWriteStream('reports/lint.html')))
		.pipe($.if(isFixed, gulp.dest(paths.src)))
		.pipe($.eslint.failAfterError());
});
