(function () {
  'use strict';

  angular.module('flexget.services').service('modal', ['$modal',
    function ($modal) {

      var defaultOptions = {
        backdrop: true,
        keyboard: true,
        modalFade: true,
        size: 'md',
        templateUrl: '/ui/static/partials/modal.html',
        headerText: 'Proceed?',
        bodyText: 'Perform this action?',
        okText: 'Ok',
        okType: 'primary',
        closeText: 'Cancel',
        closeType: 'default'
      };

      this.showModal = function (options) {
        //Create temp objects to work with since we're in a singleton service
        var tempOptions = {};
        angular.extend(tempOptions, defaultOptions, options);

        if (!tempOptions.controller) {
          tempOptions.controller = function ($scope, $modalInstance) {
            $scope.modalOptions = tempOptions;

            $scope.ok = function (result) {
              $modalInstance.close(result);
            };
            $scope.close = function (result) {
              $modalInstance.dismiss('cancel');
            };
          }
        }
        return $modal.open(tempOptions).result;
      };

    }]);
})();