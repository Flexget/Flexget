/* global angular */
(function () {
	'use strict';

	angular
		.module('blocks.exception')
		.factory('exception', exception);

	function exception($log, $q, errorService) {
		return {
			catcher: catcher
		};

		function catcher(error) {
			//Don't show toast when request failed because of auth problems
			if (error.status != 401 && error.status != 403) {
				$log.log(error.data.message);

				//TODO: Check if this needs to improve
				// return function(e) {
				/*var thrownDescription;
				var newMessage;
				if (e.data && e.data.description) {
				  thrownDescription = '\n' + e.data.description;
				  newMessage = message + thrownDescription;
				}

				e.data.description = newMessage;*/

				errorService.showToast(error.data);
			}

			return $q.reject(error.data);
		}
	}
}());