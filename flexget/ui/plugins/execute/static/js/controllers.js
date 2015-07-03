'use strict';

var executeModule = angular.module("executeModule", ['ngOboe']);

registerFlexModule(executeModule);

executeModule.filter('logclass', function () {
  return function (log) {
    var cssClass;
    switch (log.levelname) {
      case "CRITICAL":
      case "ERROR":
        cssClass = "danger";
        break;
      case "WARNING":
        cssClass = "warning";
        break;
      case "DEBUG":
        cssClass = "text-lightgrey";
        break;
      case "VERBOSE":
        cssClass = "active text-muted";
        break;
      default:
        cssClass = "default";
    }

    if (log.message.startsWith("Summary")) {
      cssClass = "info";
    }

    if (log.message.startsWith("ACCEPTED")) {
      cssClass = "success";
    }


    return cssClass;
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