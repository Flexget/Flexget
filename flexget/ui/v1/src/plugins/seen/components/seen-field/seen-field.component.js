/* global angular */
(function () {
    'use strict';

    angular
        .module('flexget.plugins.seen')
        .component('seenFields', {
            templateUrl: 'plugins/seen/compnents/seen-fields/seen-fields.tmpl.html',
            controllerAs: 'vm',
            controller: seenFieldsController,
            bindings: {
                fields: '<'
            }
        });

    function seenFieldsController() {
    }
});