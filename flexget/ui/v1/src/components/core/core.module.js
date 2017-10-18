/* global angular */
(function () {
    'use strict';

    angular
        .module('components.core', [
            'ngMaterial',

            'http-etag',            
            'blocks.router'
        ]);
}());