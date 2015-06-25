'use strict';

var executeModule = angular.module("executeModule", ['ngOboe']);

registerFlexModule(executeModule);

executeModule.controller('ExecuteCtrl', ['$scope', 'Oboe', function($scope, Oboe) {
  $scope.title = 'Execution';
  $scope.description = 'test123';
}]);


executeModule.controller('ExecuteLogCtrl', ['$scope', 'Oboe', function($scope, Oboe) {
  $scope.log = [];
  Oboe({
    url: '/api/server/log/',
    pattern: '{message}',
    start: function(stream) {
      // handle to the stream
      $scope.stream = stream;
      $scope.status = 'started';
    },
    done: function() {
      $scope.status = 'done';
    }
  }).then(function() {
    // finished loading
  }, function(error) {
    // handle errors
  }, function(node) {
    // node received
    $scope.log.push(node);
    if($scope.log.length === 1000) {
      $scope.stream.abort();
      alert('The maximum of one thousand records reached');
    }
  });
}]);
