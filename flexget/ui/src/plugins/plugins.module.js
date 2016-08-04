/* global angular */
(function () {
    'use strict';

    angular
        .module('flexget.plugins', []);
}());

//Global function used to inject plugins as dependencies
function registerPlugin(plugin) { // eslint-disable-line no-unused-vars
    angular.module('flexget.plugins').requires.push(plugin);
}