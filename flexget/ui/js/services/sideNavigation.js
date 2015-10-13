(function () {
  'use strict';

  angular.module('flexget').run(function($rootScope, $mdSidenav, $mdMedia) {
    $rootScope.toggleNav = function () {
      if ($mdSidenav('left').isLockedOpen()) {
        $rootScope.menuMini = !$rootScope.menuMini;
      } else {
        $rootScope.menuMini = false;
        $mdSidenav('left').toggle();
      }
    };

    $rootScope.closeNav = function ($event) {
      if (!$mdMedia('gt-lg')) {
        $mdSidenav('left').close();
      }
    };
  });

  angular.module('flexget.services')
    .factory('sideNav', function() {
      var items = [];

      return {
        register: function(href, caption, icon, order) {
          href = '/ui/#' + href;
          items.push({href: href, caption: caption, icon: icon, order: order})
        },
        items: items
      }
    });

})();


