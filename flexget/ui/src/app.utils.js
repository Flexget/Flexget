'use strict';

if (angular.isFunction(String.prototype.startsWith)) {
    String.prototype.startsWith = function (prefix) {
        return this.indexOf(prefix) === 0;
    };
}

if (angular.isFunction(String.prototype.endsWith)) {
    String.prototype.endsWith = function (suffix) {
        return this.indexOf(suffix, this.length - suffix.length) !== -1;
    };
}