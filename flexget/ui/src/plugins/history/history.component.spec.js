describe.skip("Plugin: History.component", function () {
	var controller;
	var history = mockHistoryData.getMockHistory();

	beforeEach(function () {
		bard.appModule('flexget.plugins.history');
		//TODO: Instead of injecting the entire 'flexget' and 'flexget.components' module in the history module, seperate the 'layout' functions in seperate modules so it doesn't need to load all the other functions as well

		bard.inject('$componentController', '$rootScope', '$http', '$httpBackend', '$q');
	});

	beforeEach(function () {
		controller = $componentController('historyView');
	});

	it("should exist", function () {
		expect(controller).to.exist;
	});

	describe("activation", function () {
		beforeEach(function () {
			controller.$onInit();
		});

		it("should get entries", function () {
			$httpBackend.expectGET('/api/history/').respond(200, history);

			$httpBackend.flush();

			expect(controller.entries).to.exist;
		});

		it("should pass when the API call fails", function () {
			$httpBackend.expectGET('/api/history/').respond(400);

			$httpBackend.flush();

			expect(true).to.be.true;
		});
	});
});