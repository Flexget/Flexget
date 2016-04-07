(function () {

  angular
    .module('flexget.home')
    .component('home', {
      templateUrl: 'components/home/home.tmpl.html',
      controllerAs: 'vm',
      controller: homeController,
    })

    function homeController(errorService) {
    	var vm = this;

    	vm.openToast = function() {
    		console.log(errorService);

    		var params = {
    			text: "Test"
    		}

    		errorService.showToast(params);
    	}
    }
})();
