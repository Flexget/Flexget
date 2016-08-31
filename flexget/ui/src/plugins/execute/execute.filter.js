/* global angular */
(function () {
    'use strict';

    angular
        .module('plugins.execute')
        .filter('executePhaseFilter', executePhaseFilter);

    function executePhaseFilter() {
        var phaseDescriptions = {
            input: 'Gathering Entries',
            metainfo: 'Figuring out meta data',
            filter: 'Filtering Entries',
            download: 'Downloading Accepted Entries',
            modify: 'Modifying Entries',
            output: 'Executing Outputs',
            exit: 'Finished'
        };

        return function (phase) {
            if (phase in phaseDescriptions) {
                return phaseDescriptions[phase];
            } else {
                return 'Processing';
            }
        };
    }

}());