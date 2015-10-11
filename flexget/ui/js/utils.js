'use strict';

String.prototype.startsWith = function(prefix) {
  return this.indexOf(prefix) === 0;
};

function registerModule(module) {
  angular.module('flexget').requires.push(module.name);
}