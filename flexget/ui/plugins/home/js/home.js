(function () {
  'use strict';

  var homeModule = angular.module("homeModule", ['angular.filter']);
  registerModule(homeModule);

  homeModule.run(function(route) {
    route.register('home', '/home', null, 'plugin/home/static/index.html');
  });
})();