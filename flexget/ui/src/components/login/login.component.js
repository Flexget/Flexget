(function () {

	angular
		.module('components.login')
		.component('login', {
			templateUrl: 'components/login/login.tmpl.html',
			controllerAs: 'vm',
			controller: loginController
		});

	function loginController($stateParams, loginService, $state) {
		var vm = this;

		vm.timeout = $stateParams.timeout;
        vm.login = login;
		vm.credentials = {};

		function login() {
            loginService.login(vm.credentials, vm.remember)
				.then(function () {
					//TODO: Route to previous requested route
					$state.go('flexget.home');
				})
                .catch(function (data) {
                    vm.credentials.password = '';
                    if (data.message) {
                        vm.error = data.message;
                    } else {
                        vm.error = 'Error during authentication';
                    }
                });
        };
	};
})();