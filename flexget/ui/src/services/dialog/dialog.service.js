(function () {
    'use strict';

    angular.module('flexget.services')
        .factory('Dialog', DialogFactory);

    function DialogFactory ($mdDialog) {
        return {
            open: function (locals) {
                return $mdDialog.show({
                    templateUrl: '/services/dialog/dialog.tmpl.html',
                    controller: 'DialogController',
                    locals: {
                       options: locals
                    },
                    controllerAs: 'vm'
                });
            },
        }
    };
})();