// Karma configuration
// Generated on Tue May 24 2016 11:03:15 GMT+0200 (CEST)

module.exports = function (config) {
  config.set({
    // base path that will be used to resolve all patterns (eg. files, exclude)
    basePath: '',

    // frameworks to use
    // available frameworks: https://npmjs.org/browse/keyword/karma-adapter
    frameworks: ['wiredep', 'mocha', 'chai', 'sinon', 'chai-sinon'],

    wiredep: {
      dependencies: true,
      devDependencies: true,
    },

    // list of files / patterns to load in the browser
    files: [
      'tests-mock-data/**/*.js',
      'src/app.loading.js',
      'src/app.utils.js',
      'src/app.module.js',
      'src/**/*.module.js',
      'src/**/*.js',
    ],

    // list of files to exclude
    exclude: [],

    // preprocess matching files before serving them to the browser
    // available preprocessors: https://npmjs.org/browse/keyword/karma-preprocessor
    preprocessors: {
      'src/**/!(*.spec).js': ['coverage'],
    },

    // test results reporter to use
    // possible values: 'dots', 'progress'
    // available reporters: https://npmjs.org/browse/keyword/karma-reporter
    reporters: ['dots', 'coverage'],

    coverageReporter: {
      type: 'lcovonly',
      dir: '.',
      file: 'webui-coverage.info',
      subdir: '.',
    },

    // web server port
    port: 9876,

    // enable / disable colors in the output (reporters and logs)
    colors: true,

    // level of logging
    // possible values: config.LOG_DISABLE || config.LOG_ERROR || config.LOG_WARN || config.LOG_INFO || config.LOG_DEBUG
    logLevel: config.LOG_INFO,

    // enable / disable watching file and executing tests whenever any file changes
    autoWatch: true,

    // start these browsers
    // available browser launchers: https://npmjs.org/browse/keyword/karma-launcher
    browsers: ['PhantomJS'],

    // Continuous Integration mode
    // if true, Karma captures browsers, runs the tests and exits
    singleRun: true,

    // Concurrency level
    // how many browser should be started simultaneous
    concurrency: Infinity,
  });
};
