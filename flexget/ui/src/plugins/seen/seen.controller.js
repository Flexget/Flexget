(function () {
  'use strict';

  angular
    .module('flexget.plugins.seen')
    .controller('seenController', seenController);

  function seenController($http) {
    var vm = this;

    vm.title = 'Seen';

    $http.get('/api/seen')
      .success(function handleSeen(data) {
        vm.entries = data.seen_entries;
      })
      .error(function handlerSeenError(data) {
        // log error
      });
  }
})();
