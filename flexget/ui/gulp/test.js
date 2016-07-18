'use strict';

var gulp = require('gulp');

var paths = gulp.paths;

var $ = require('gulp-load-plugins')();

var browserSync = require('browser-sync').create();

gulp.task('serve-specs', ['build-specs'], function (done) {

    gulp.watch([paths.src + '/**/*.js', paths.spechelpers + '/**/*.js'], function () {
        browserSync.reload();
    });

    var options = {
        //proxy: 'localhost:3050',
        port: 3050,
        files: [],
        injectChanges: true,
        logFileChanges: true,
        logLevel: 'info',
        logPrefix: 'Flexget',
        notify: true,
        reloadDelay: 0,
        startPath: 'specs.html',
        server: '.'
    };

    browserSync.init(options);

    done();
});

gulp.task('build-specs', function () {
    var wiredep = require('wiredep').stream;
    var wiredepOptions = {
        directory: 'bower_components',
        ignorepath: '../',
        exclude: [/angular-material\.css/],
        devDependencies: true
    };

    var injectScripts = gulp.src([
        paths.src + '/**/*.js',
        '!' + paths.src + '/app.utils.js',
        '!' + paths.src + '/app.loading.js',
        '!' + paths.src + '/app.module.js',
        '!' + paths.src + '/**/*.spec.js',
    ]).pipe($.angularFilesort());

    var specHelpers = gulp.src([
        paths.spechelpers + '/**/*.js'
    ]);

    var specs = gulp.src([
        paths.src + '/**/*.spec.js'
    ]);

    return gulp.src(paths.specs + '/specs.html')
        .pipe($.inject(injectScripts))
        .pipe(wiredep(wiredepOptions))
        .pipe($.inject(specHelpers, { starttag: '<!-- inject:spechelpers:{{ext}} -->' }))
        .pipe($.inject(specs, { starttag: '<!-- inject:specs:{{ext}} -->'}))
        .pipe(gulp.dest(paths.specs));
});