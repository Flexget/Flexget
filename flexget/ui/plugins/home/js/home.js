(function () {
  'use strict';

  var homeModule = angular.module("homeModule", ['angular.filter']);
  registerModule(homeModule);

  homeModule.config(function(routeProvider) {
    routeProvider.register('home', '/home', null, 'plugin/home/static/index.html');
  });
})();