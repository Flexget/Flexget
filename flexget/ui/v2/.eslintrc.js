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
    'import/no-extraneous-dependencies':[ 'error', { devDependencies: true } ],
    'import/prefer-default-export': 'off',
    'comma-dangle': ['error', {
      arrays: 'always-multiline',
      objects: 'always-multiline',
      imports: 'always-multiline',
      exports: 'always-multiline',
      functions: 'ignore',
    }],
    'import/no-named-as-default': 'off',
    'react/no-array-index-key': 'off',
    'no-constant-condition': 'off',
  }
};
