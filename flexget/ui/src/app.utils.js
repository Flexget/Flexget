'use strict';

String.prototype.startsWith = function (prefix) {
    return this.indexOf(prefix) === 0;
};

function registerPlugin(plugin) {
    angular.module('flexget').requires.push(plugin.name);
}