const BundleAnalyzerPlugin = require('webpack-bundle-analyzer').BundleAnalyzerPlugin;
const ExtractTextPlugin = require('extract-text-webpack-plugin');
const FaviconsWebpackPlugin = require('favicons-webpack-plugin');
const HtmlWebpackPlugin = require('html-webpack-plugin');
const webpack = require('webpack');
const path = require('path');
const config = require('./webpack.shared');

config.output = {
  path: path.join(__dirname, 'dist', 'assets'),
  filename: '[name].[chunkhash].js',
  publicPath: '/v2/assets/',
};
config.plugins = [
  new FaviconsWebpackPlugin(path.resolve('./src/favicon.png')),
  new webpack.DefinePlugin({
    'process.env': {
      NODE_ENV: JSON.stringify('production'),
    },
  }),
  new webpack.optimize.CommonsChunkPlugin({ name: ['vendor', 'manifest'], minChunks: Infinity }),
  new webpack.optimize.MinChunkSizePlugin({ minChunkSize: 8192 }),
  new HtmlWebpackPlugin({
    title: 'FlexGet Manager v2',
    filename: '../index.html',
    template: './src/index.ejs',
    base: '/v2/',
  }),
  new webpack.optimize.UglifyJsPlugin({
    compress: {
      screw_ie8: true,
      warnings: false,
    },
    mangle: {
      screw_ie8: true,
    },
    output: {
      comments: false,
      screw_ie8: true,
    },
    sourceMap: false,
  }),
  new ExtractTextPlugin({
    filename: '[name].[chunkhash].css',
    allChunks: true,
  }),
  ...process.env.DEBUG ? [new BundleAnalyzerPlugin({
    analyzerMode: 'server',
  })] : [],
];
config.module.rules.push({
  test: /\.s?css$/,
  loader: ExtractTextPlugin.extract(['css-loader', 'resolve-url-loader']),
});

module.exports = config;
