describe('Home Component:', function () {
	var component;

	beforeEach(function () {
		bard.appModule('components.home');
		bard.inject('$componentController');
	});

	beforeEach(function () {
		component = $componentController('home');
	});

	it("should exist", function () {
		expect(component).to.exist;
	});
});