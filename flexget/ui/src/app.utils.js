'use strict';

if (typeof String.prototype.startsWith !== 'function') {
    String.prototype.startsWith = function (prefix) { // eslint-disable-line no-extend-native
        return this.indexOf(prefix) === 0;
    };
}

if (typeof String.prototype.endsWith !== 'function') {
    String.prototype.endsWith = function (suffix) { // eslint-disable-line no-extend-native
        return this.indexOf(suffix, this.length - suffix.length) !== -1;
    };
}