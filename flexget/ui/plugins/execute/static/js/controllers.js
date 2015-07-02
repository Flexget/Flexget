'use strict';

var executeModule = angular.module("executeModule", ['ngOboe']);

registerFlexModule(executeModule);

executeModule.filter('logclass', function () {
  return function (levelname) {
    var level;
    switch (levelname) {
      case "CRITICAL":
      case "ERROR":
        level = "danger";
        break;
      case "WARNING":
        level = "warning";
        break;
      case "DEBUG":
        level = "text-muted text-lightgrey";
        break;
      case "VERBOSE":
        level = "active text-muted";
        break;
      default:
        level = "default";
    }
    return level;
  }
});

executeModule.controller('ExecuteCtrl', ['$scope', 'Oboe', function($scope, Oboe) {
  $scope.title = 'Execution';
  $scope.description = 'test123';
}]);


executeModule.controller('ExecuteLogCtrl', ['$scope', 'Oboe', function($scope, Oboe) {
  $scope.log = [];
  var logStream;

  Oboe({
    url: '/api/server/log/',
    pattern: '{message}',
    start: function(stream) {
      logStream = stream;
    }
  }).then(function() {
    // finished loading
  }, function(error) {
    // handle errors
  }, function(node) {
    $scope.log.push(node);
  });

  $scope.$on("$destroy", function() {
    if (logStream) {
      logStream.abort();
    }
  });
}]);


executeModule.controller('ExecuteHistoryCtrl', ['$scope', 'Oboe', function($scope, Oboe) {
  $scope.title = 'Execution History';
  $scope.description = 'test123';
}]);