(function () {
	'use strict';

	angular
		.module('blocks.exception')
		.factory('exception', exception);

	function exception($q, $log) {
		var service = {
			catcher: catcher
		};
		return service;

		function catcher(error) {
			$log.log(error.data.message);

			//TODO: Make this better: show toasts with the message, and popup with more info
			// Also, when this gets implemented, stub out the functions in the tests so it doesn't call all the log or toast functions		

			// return function(e) {
			/*var thrownDescription;
			var newMessage;
			if (e.data && e.data.description) {
			  thrownDescription = '\n' + e.data.description;
			  newMessage = message + thrownDescription;
			}
			e.data.description = newMessage;
			//logger.error(newMessage);*/
			return $q.reject(error);
			//};
		}
	}
})();