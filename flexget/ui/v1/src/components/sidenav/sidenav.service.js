/* global angular */
(function () {
    'use strict';

    angular
        .module('components.sidenav')
        .factory('sideNavService', sideNavService);

    function sideNavService($http, $mdMedia, $mdSidenav, $rootScope, exception) {
        return {
            toggle: toggle,
            close: close,
            getVersionInfo: getVersionInfo
        };

        function toggle() {
            if ($mdSidenav('left').isLockedOpen()) {
                $rootScope.menuMini = !$rootScope.menuMini;
            } else {
                $rootScope.menuMini = false;
                $mdSidenav('left').toggle();
            }
        }

        function close() {
            if (!$mdMedia('gt-lg')) {
                $mdSidenav('left').close();
            }
        }

        function getVersionInfo() {
            return $http.get('/api/server/version/')
                .then(getVersionInfoComplete)
                .catch(callFailed);
            
            function getVersionInfoComplete(response) {
                return response.data;
            }
        }

        function callFailed(error) {
            return exception.catcher(error);
        }
    }
}());