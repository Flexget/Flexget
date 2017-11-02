const path = require('path');

module.exports = {
  entry: {
    main: [
      'babel-polyfill',
      'whatwg-fetch',
      './src/app.jsx',
    ],
    vendor: [
      'redux',
      'react-redux',
      'react-router',
      'react-router-dom',
      'react',
      'react-dom',
      'redux-saga',
    ],
  },
  resolve: {
    extensions: ['.js', '.jsx'],
    modules: [
      path.resolve('./src'),
      'node_modules',
    ],
  },
  module: {
    rules: [
      {
        test: /\.jsx?$/,
        loaders: ['babel-loader'],
        exclude: /node_modules/,
      },
      {
        test: /\.md$/,
        loaders: ['html-loader', 'markdown-loader'],
      },
      {
        test: /\.woff(2)?(\?v=[0-9]\.[0-9]\.[0-9])?$/,
        loader: 'url-loader?limit=10000&mimetype=application/font-woff',
      },
      {
        test: /\.(ttf|eot|svg)(\?v=[0-9]\.[0-9]\.[0-9])?$/,
        loader: 'file-loader',
      },
      {
        test: /\.(gif|png|jpg|jpeg)(\?[a-z0-9]+)?$/,
        loader: 'url-loader?limit=8192',
      },

    ],
  },
};
