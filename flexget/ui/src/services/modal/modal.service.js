(function () {
    'use strict';

    angular.module('flexget.services')
        .service('modal', modalService);

    function modalService($modal) {

        var defaultOptions = {
            backdrop: true,
            keyboard: true,
            modalFade: true,
            size: 'md',
            templateUrl: 'services/modal/modal.tmpl.html',
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
                tempOptions.controller = function ($modalInstance) {
                    vm = this;

                    vm.modalOptions = tempOptions;

                    vm.ok = function (result) {
                        $modalInstance.close(result);
                    };
                    vm.close = function (result) {
                        $modalInstance.dismiss('cancel');
                    };
                }
            }

            tempOptions.controllerAs = 'vm';

            return $modal.open(tempOptions).result;
        };

    }

})();