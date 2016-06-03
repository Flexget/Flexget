(function () {
    'use strict';

    angular.module('components.sidenav')
        .factory('sideNavService', sideNavService);

    function sideNavService($rootScope, $mdSidenav, $mdMedia) {
		return {
            toggle: toggle,
            close: close
        };

        function toggle() {
            if ($mdSidenav('left').isLockedOpen()) {
                $rootScope.menuMini = !$rootScope.menuMini;
            } else {
                $rootScope.menuMini = false;
                $mdSidenav('left').toggle();
            }
        };

        function close() {
			console.log('close');
            if (!$mdMedia('gt-lg')) {
                $mdSidenav('left').close();
            }
        };
	};
})();