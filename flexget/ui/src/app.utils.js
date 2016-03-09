'use strict';

String.prototype.startsWith = function (prefix) {
  return this.indexOf(prefix) === 0;
};

function registerPlugin(plugin) { // eslint-disable-line no-unused-vars
  angular.module('flexget').requires.push(plugin.name);
}
