(function () {
	'use strict';

	angular
		.module('blocks.exception')
		.factory('exception', exception);

	function exception($q, $log, errorService) {
		var service = {
			catcher: catcher
		};
		return service;

		function catcher(error) {
			$log.log(error.data.message);

			// return function(e) {
			/*var thrownDescription;
			var newMessage;
			if (e.data && e.data.description) {
			  thrownDescription = '\n' + e.data.description;
			  newMessage = message + thrownDescription;
			}

			e.data.description = newMessage;*/

			errorService.showToast(error.data);
			return $q.reject(error.data);
			//};
		}
	}
})();