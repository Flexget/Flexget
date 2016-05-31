(function () {
    'use strict';

    angular
        .module('flexget.components', [
            'ui.router',
            'ngMaterial',
			'flexget.components.requestInterceptor'
		]);
})();