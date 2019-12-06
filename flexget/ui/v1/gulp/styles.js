/* eslint-disable no-console */
'use strict';

var gulp = require('gulp');
var paths = gulp.paths;
var $ = require('gulp-load-plugins')();

gulp.task('styles', function () {

    var sassOptions = {
        style: 'expanded',
        includePaths: [
            'bower_components'
        ]
    };

    var injectFiles = gulp.src([
        paths.src + '/**/*.scss',
        '!' + paths.src + '/app.scss',
        '!' + paths.src + '/**/_*.scss',
        '!' + paths.src + '/scss/flexget.scss'
    ], {read: false});

    var injectOptions = {
        transform: function (filePath) {
            filePath = filePath.replace(paths.src + '/app/', '');
            return '@import \'' + filePath + '\';';
        },
        starttag: '// injector',
        endtag: '// endinjector',
        addRootSlash: false
    };

    var indexFilter = $.filter('app.scss', {
        restore: true
    });

    return gulp.src([
            paths.src + '/app.scss'
        ])
        .pipe(indexFilter)
        .pipe($.inject(injectFiles, injectOptions))
        .pipe(indexFilter.restore)
        .pipe($.sass(sassOptions))
        .pipe($.autoprefixer({browsers: ['> 1%', 'last 2 versions', 'Firefox ESR', 'Opera 12.1']}))
        .on('error', function handleError(err) {
            console.error(err.toString());
            this.emit('end');
        })
        .pipe(gulp.dest(paths.tmp + '/serve/styles'));
});
