describe("Toolbar Component:", function () {
	var component;

	beforeEach(function () {
		bard.appModule('components.toolbar');
		bard.inject('$componentController', 'routerHelper', 'sideNavService', '$rootScope');

		sinon.stub(sideNavService, 'toggle');
	});

	beforeEach(function () {
		component = $componentController('toolBar');
	});

	it("should exist", function () {
		expect(component).to.exist;
	});

	describe('toggle', function () {
		it('should exist', function () {
			expect(component.toggle).to.exist;
		});

		it('should call the sideNav toggle function', function () {
			component.toggle();
			
			expect(sideNavService.toggle).to.have.been.calledOnce;
		});
	});
});