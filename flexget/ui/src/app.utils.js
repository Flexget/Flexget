'use strict';

if (typeof String.prototype.startsWith !== 'function') {
    String.prototype.startsWith = function (prefix) {
        return this.indexOf(prefix) === 0;
    };
}

if (typeof String.prototype.endsWith !== 'function') {
    String.prototype.endsWith = function (suffix) {
        return this.indexOf(suffix, this.length - suffix.length) !== -1;
    };
}

function registerPlugin(plugin) { // eslint-disable-line no-unused-vars
    angular.module('flexget').requires.push(plugin.name);
}