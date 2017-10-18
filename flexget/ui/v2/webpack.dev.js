const HtmlWebpackPlugin = require('html-webpack-plugin');
const FaviconsWebpackPlugin = require('favicons-webpack-plugin');
const webpack = require('webpack');
const path = require('path');
const config = require('./webpack.shared');

config.entry.main.push(
  'webpack/hot/dev-server',
  `webpack-dev-server/client?http://localhost:${process.env.PORT || 8000}`
);

config.output = {
  path: __dirname,
  filename: '[name].bundle.js',
  publicPath: '/',
};
config.devtool = 'source-map';
config.plugins = [
  new FaviconsWebpackPlugin(path.resolve('./src/favicon.png')),
  new webpack.HotModuleReplacementPlugin(),
  new webpack.NoEmitOnErrorsPlugin(),
  new webpack.NamedModulesPlugin(),
  new webpack.DefinePlugin({
    'process.env': {
      NODE_ENV: JSON.stringify('development'),
    },
  }),
  new HtmlWebpackPlugin({
    title: 'FlexGet Manager v2',
    template: './src/index.ejs',
    base: '/',
  }),
];
config.module.rules.push({
  test: /\.s?css$/,
  loaders: ['style-loader', 'css-loader', 'resolve-url-loader'],
});

module.exports = config;
