(function () {
    'use strict';

    angular.module('flexget.components')
        .run(userConfig);

    function userConfig(toolBar) {
        toolBar.registerMenuItem('Manage', 'Profile', 'fa fa-user', function () {
            alert('not implemented yet')
        }, 100);
    }

})();


