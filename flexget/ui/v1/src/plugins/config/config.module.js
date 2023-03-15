/* global angular, registerPlugin */
(function () {
    'use strict';

    angular
        .module('plugins.config', [
            'ngMaterial',

            'ab-base64',

            'blocks.exception',
            'blocks.router',
            'components.toolbar',

            'ui.ace'
        ]);

    registerPlugin('plugins.config');
}());