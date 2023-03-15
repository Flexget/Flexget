'use strict';

var gulp = require('gulp');
var path = require('path');

var paths = gulp.paths;

var $ = require('gulp-load-plugins')({
    pattern: ['gulp-*', 'main-bower-files', 'uglify-save-license', 'del']
});

gulp.task('partials', function () {
    return gulp.src([
            paths.src + '/**/*.html',
            '!' + paths.src + '/app.html'
        ])
        .pipe($.minifyHtml({
            empty: true,
            spare: true,
            quotes: true
        }))
        .pipe($.angularTemplatecache('templateCacheHtml.js', {
            module: 'flexget',
            root: ''
        }))
        .pipe(gulp.dest(paths.tmp + '/partials/'));
});

gulp.task('html', ['inject', 'partials'], function () {
    var partialsInjectFile = gulp.src(paths.tmp + '/partials/templateCacheHtml.js', {read: false});
    var partialsInjectOptions = {
        starttag: '<!-- inject:partials -->',
        ignorePath: paths.tmp + '/partials',
        addRootSlash: false
    };

    var htmlFilter = $.filter(['*.html'], {restore: true});
    var jsFilter = $.filter('**/*.js', {restore: true});
    var cssFilter = $.filter('**/*.css', {restore: true});

    return gulp.src(paths.tmp + '/serve/*.html')
        .pipe($.inject(partialsInjectFile, partialsInjectOptions))
        .pipe($.useref())
        .pipe(jsFilter)
        .pipe($.ngAnnotate())
        //.pipe($.uglify({preserveComments: $.uglifySaveLicense}))
        .pipe(jsFilter.restore)
        .pipe(cssFilter)
        .pipe($.csso())
        .pipe(cssFilter.restore)
        .pipe($.replace('url(ui-grid', 'url(../fonts/ui-grid'))
        .pipe($.replace('../bower_components/font-awesome/fonts', '../fonts'))
        .pipe($.replace('../bower_components/material-design-iconic-font/dist/fonts', '../fonts'))
        .pipe($.revReplace())
        .pipe(htmlFilter)
        .pipe($.minifyHtml({
            empty: true,
            spare: true,
            quotes: true
        }))
        .pipe(htmlFilter.restore)
        .pipe(gulp.dest(paths.dist + '/'))
        .pipe($.size({title: paths.dist + '/', showFiles: true}));
});

gulp.task('images', function () {
    return gulp.src(paths.src + '/assets/images/**/*')
        .pipe(gulp.dest(paths.dist + '/assets/images/'));
});

gulp.task('fonts', function () {
    return gulp.src($.mainBowerFiles())
        .pipe($.filter('**/*.{eot,otf,svg,ttf,woff,woff2}'))
        .pipe($.flatten())
        .pipe(gulp.dest(paths.dist + '/fonts/'));
});

gulp.task('translations', function () {
    return gulp.src('src/**/il8n/*.json')
        .pipe(gulp.dest(paths.dist + '/'))
        .pipe($.size());
});

gulp.task('misc', function () {
    return gulp.src(paths.src + '/favicon.ico')
        .pipe(gulp.dest(paths.dist + '/'));
});

gulp.task('clean', function () {
    return $.del([path.join(paths.dist, '/'), path.join(paths.tmp, '/')]);
});

gulp.task('buildapp', ['html', 'images', 'fonts', 'misc']);
