(function () {
  'use strict';

  var userPlugin = angular.module('userPlugin', ['ngCookies']);
  registerModule(userPlugin);

  userPlugin.run(function($state, toolBar, $http) {
    var logout = function() {
      $http.get('/api/logout/')
        .success(function (data, status, headers, config) {
          $state.go('login');
        });
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


