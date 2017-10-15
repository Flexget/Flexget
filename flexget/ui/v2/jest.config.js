module.exports = {
  collectCoverageFrom: [
    'src/**/*.{js,jsx}',
    '!src/js/store/*.js',
    '!src/js/store/series/*.js',
    '!src/js/{app,history,root,theme}.{js,jsx}',
    '!src/js/utils/*.{js,jsx}',
    '!**/node_modules/**',
    '!**/dist/**',
    '!src/js/store/**/shapes.js',
  ],
  coverageThreshold: {
    global: {
      branches: 40,
      functions: 40,
      lines: 40,
      statements: 40,
    },
  },
  moduleFileExtensions: [
    'js',
    'jsx',
  ],
  moduleDirectories: [
    'node_modules',
    'src',
    'src/js',
  ],
  moduleNameMapper: {
    '\\.css$': 'identity-obj-proxy',
    '\\.(gif|ttf|eot|svg|png)$': '<rootDir>/src/js/__mocks__/fileMock.js',
  },
  setupFiles: [
    'raf/polyfill',
    '<rootDir>/src/js/utils/tests/setupFiles.js',
  ],
  setupTestFrameworkScriptFile: '<rootDir>/src/js/utils/tests/setupTest.js',
};
