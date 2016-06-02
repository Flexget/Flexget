describe('Home Routes: ', function () {
	
    beforeEach(function () {
		//Create abstract parent state first
		//TODO: create funcion for this, so we can just call the function and not need to inject the entire block everywhere
		module('ui.router', function ($stateProvider) {
			$stateProvider.state('flexget', { abstract: true });
		});
		module('components.home');
		bard.inject('$state', '$templateCache', '$rootScope', '$location');
    });

    it("should map state 'flexget.home' to url #/", function () {
		expect($state.href('flexget.home', {})).to.equal('#/');
    });
	
	it("should map state to the 'home' component", function () {
		expect($state.get('flexget.home').component).to.equal('home');
	});
	
	describe("Transitions", function() {
		it("should work with $state.go", function () {
			$state.go('flexget.home');
			$rootScope.$apply();
			expect($state.is('flexget.home')).to.be.true;
		});
		
		it("should work with '' path", function() {
			$location.path('');
			$rootScope.$apply();
			expect($state.is('flexget.home')).to.be.true;
		});
		
		it("should work with '/' path", function() {
			$location.path('/');
			$rootScope.$apply();
			expect($state.is('flexget.home')).to.be.true;
		});
	});
});