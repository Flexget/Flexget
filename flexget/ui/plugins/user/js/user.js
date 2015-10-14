(function () {
  'use strict';

  var userPlugin = angular.module('userPlugin', ['ngCookies']);
  registerModule(userPlugin);

  userPlugin.run(function($state, toolBar, $http) {
    toolBar.registerMenuItem('Manage', 'Profile', 'fa fa-user', function(){alert('not implemented yet')}, 100);
  });
})();


