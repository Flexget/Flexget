describe('404 Component:', function () {
	var component;

	beforeEach(function () {
		module('components.404');
		bard.inject('$state', '$componentController');
		sinon.stub($state, 'go');
	});

	beforeEach(function () {
		component = $componentController('notFound');
	});

	it("should exist", function () {
		expect(component).to.exist;
	});

	describe("goHome()", function () {
		it('should exist', function () {
			expect(component.goHome).to.exist;
		});

		it('should trigger a reroute to home', function () {
			component.goHome();

			expect($state.go).to.have.been.calledOnce;
			expect($state.go).to.have.been.calledWith('flexget.home');
		});
	});
});