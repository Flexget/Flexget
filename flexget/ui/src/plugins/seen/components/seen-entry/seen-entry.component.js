/* global angular */
(function () {
    'use strict';

    angular
        .module('plugins.seen')
        .component('seenEntry', {
            templateUrl: 'plugins/seen/components/seen-entry/seen-entry.tmpl.html',
            controllerAs: 'vm',
            bindings: {
                entry: '<',
                deleteEntry: '&'
            }
        });
}());