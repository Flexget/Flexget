describe("Service: Schedule", function () {
	beforeEach(function () {
		bard.appModule('plugins.schedule');

		bard.inject('$httpBackend', 'schedulesService', 'exception', 'CacheFactory');

		sinon.stub(exception, 'catcher');
		
		CacheFactory.clearAll();
	});

	it("should exist", function () {
		expect(schedulesService).to.exist;
	});

	describe('getLists()', function () {
		it("should issue a GET /api/schedules/ request", function () {
			$httpBackend.expect('GET', '/api/schedules/').respond(200, {});
			schedulesService.getSchedules().then(function (data) {
				expect(data).to.exist;
			});
			$httpBackend.flush();
		});

		it("should report an error if request fails", function () {
			$httpBackend.expect('GET', '/api/schedules/').respond(500, {
				message: "Request failed"
			});
			schedulesService.getSchedules().catch(function (error) {
				expect(error.data.message).to.equal("Request failed");
				expect(exception.catcher).to.have.been.calledOnce;
			});
			$httpBackend.flush();
		});
	});
});