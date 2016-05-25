describe("Layout: Sidenav.component", function () {
	var controller;
	var mockStates = mockStatesData.getStates();

	beforeEach(function () {
		module('flexget.layout');
		bard.inject('$componentController', 'routerHelper');
	});

	beforeEach(function () {
		console.log(mockStates);
		routerHelper.configureStates(mockStates, '/');
		controller = $componentController('sideNav');
	});

	it("should exist", function () {
		expect(controller).to.exist;
	});

	describe("after activation", function () {
		beforeEach(function () {
			controller.$onInit();
		});

		it("should have items", function () {
			expect(controller.navItems).to.exist;
			expect(controller.navItems).to.have.length.above(0);
		});

		it("should filter the sidebar items correctly", function () {
			expect(controller.navItems).to.have.length(mockStates.length - 1);
		});
	});
});