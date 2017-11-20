/* global angular */
(function () {
    'use strict';
    
    angular
        .module('blocks.pagination')
        .filter('makeRange', makeRangeFilter);
    
    function makeRangeFilter() {
        return function (input) {
            var lowBound = parseInt(input[0], 10);
            var highBound = parseInt(input[1], 10);

            var result = [];

            for (var i = lowBound; i <= highBound; i++) { result.push(i); }
            return result;
        };
    }
})();