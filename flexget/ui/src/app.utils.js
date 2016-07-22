'use strict';

if (typeof String.prototype.startsWith !== 'function') { // eslint-disable-line no-extend-native
    String.prototype.startsWith = function (prefix) {
        return this.indexOf(prefix) === 0;
    };
}

if (typeof String.prototype.endsWith !== 'function') { // eslint-disable-line no-extend-native
    String.prototype.endsWith = function (suffix) {
        return this.indexOf(suffix, this.length - suffix.length) !== -1;
    };
}