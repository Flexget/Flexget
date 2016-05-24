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

window.loadingScreen = window.pleaseWait({
        logo: "assets/images/header.png",
        backgroundColor: '#FFFFFF',
        loadingHtml: '' +
        '<p class="text-primary text-bold">Loading</p>' +
        '<div class="spinner">' +
        '<div class="rect1"></div><div class="rect2"></div><div class="rect3"></div>' +
        '<div class="rect4"></div><div class="rect5"></div>' +
        '</div>'
    });
