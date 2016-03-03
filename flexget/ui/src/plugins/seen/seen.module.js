(function () {
  'use strict';

  var seenModule = angular.module(
    'flexget.plugins.seen',
    ['schemaForm']
  );

  registerPlugin(seenModule);

  seenModule.run(function run(route, sideNav) {
    route.register('seen', '/seen', 'seenController', 'plugins/seen/seen.tmpl.html');
    sideNav.register('/seen', 'Seen', 'fa fa-eye', 228);
  });
})();
