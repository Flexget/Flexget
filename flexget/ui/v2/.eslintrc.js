module.exports = {
  extends: [
    'airbnb',
  ],
  parser: "babel-eslint",
  plugins: [
    'jest',
  ],
  env: {
    browser: true,
    node: true,
    'jest/globals': true,
  },
  ecmaFeatures: {
    jsx: true,
    es6: true,
  },
  settings: {
    'import/resolver': {
      webpack: {
        config: 'webpack.shared.js'
      }
    }
  },
  rules: {
    'react/forbid-prop-types': 'off',
    'react/jsx-no-bind': 'off',
  }
};
