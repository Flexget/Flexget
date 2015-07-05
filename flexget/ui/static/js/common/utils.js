'use strict';

String.prototype.startsWith = function(prefix) {
    return this.indexOf(prefix) === 0;
};

function registerFlexModule(module) {
  angular.module('flexgetApp').requires.push(module.name);
}