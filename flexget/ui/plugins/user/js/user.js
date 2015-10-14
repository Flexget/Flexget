(function () {
  'use strict';

  var userPlugin = angular.module('userPlugin', ['ngCookies']);
  registerModule(userPlugin);

  userPlugin.run(function($state, $cookieStore, $cookies, toolBar) {
    var logout = function() {
      $cookieStore.remove('flexgetToken');
      $state.go('login');
    };

    var menu = {
      width: 2,
      items: [
        {label: 'Profile', cssClass: 'fa fa-user', action: function(){alert('not implemented yet')}},
        {label: 'Logout', cssClass: 'fa fa-sign-out', action: logout}
      ]
    };

    toolBar.registerMenu('Manage', 'fa fa-cog', menu, 255);
  });
})();


