(function () {
    'use strict';

    angular.module('flexget.services')
        .controller('DialogController', DialogController);

    function DialogController ($mdDialog, options) {
        var vm = this;

        vm.options = options;

        this.cancel = function() {
            $mdDialog.cancel();
        };

        this.hide = function(answer) {
            $mdDialog.hide(answer);
        };
    };
})();