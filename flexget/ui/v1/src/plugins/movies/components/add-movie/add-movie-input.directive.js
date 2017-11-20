/* global angular */
(function () {
    'use strict';

    angular
        .module('plugins.movies')
        .directive('inputClear', inputClear);

    function inputClear() {
        return {
            restrict: 'A',
            compile: function (element, attrs) {
                var color = attrs.inputClear;
                var style = color ? "color:" + color + ";" : "";
                var action = attrs.ngModel + " = ''";
                element.after(
                    '<md-button class="animate-show md-icon-button md-accent"' +
                    'ng-show="' + attrs.ngModel + '" ng-click="' + action + '"' +
                    'style="position: absolute; top: 0px; right: -6px;">' +
                    '<div style="' + style + '">x</div>' +
                    '</md-button>');
            }
        };
    }
} ());