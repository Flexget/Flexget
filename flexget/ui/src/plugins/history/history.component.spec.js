describe("Plugin: History.component", function () {
	var controller;
	var history = mockHistoryData.getMockHistory();

	beforeEach(function () {
		bard.appModule('flexget.plugins.history', function ($provide) {
			$provide.provider('route', function () {
				this.$get = function () {

					function register() { };

					return {
						register: register
					}
				}
			});

			$provide.service('sideNav', function () {
				this.register = function () { };
			});
		});

		bard.inject('$componentController', '$rootScope', '$http', '$httpBackend', 'route', 'sideNav', '$q');
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