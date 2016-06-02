describe('404 Routes: ', function () {
	
    beforeEach(function () {
		//Create abstract parent state first
		//TODO: create funcion for this, so we can just call the function and not need to inject the entire block everywhere
		module('ui.router', function ($stateProvider) {
			$stateProvider.state('flexget', { abstract: true });
		});
		module('components.404');
		bard.inject('$state', '$templateCache', '$rootScope', '$location');
    });

    it("should map state 'flexget.404' to url #/", function () {
		expect($state.href('flexget.404', {})).to.equal('#/404');
    });
	
	it("should map state route to the 'notFound' component", function () {
		expect($state.get('flexget.404').component).to.equal('notFound');
	});
	
	describe("Transitions", function() {
		it("should work with $state.go", function () {
			$state.go('flexget.404');
			$rootScope.$apply();
			expect($state.is('flexget.404')).to.be.true;
		});
		
		it("should work with '/404' path", function() {
			$location.path('/404');
			$rootScope.$apply();
			expect($state.is('flexget.404')).to.be.true;
		});
		
		it("should work with '/unkown' path", function() {
			$location.path('/unkown');
			$rootScope.$apply();
			expect($state.is('flexget.404')).to.be.true;
		});
	});
});