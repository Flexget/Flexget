describe("Service: History", function () {
	beforeEach(function () {
		bard.appModule('plugins.history');

		bard.inject('$httpBackend', 'historyService', 'exception', 'CacheFactory');

		sinon.stub(exception, 'catcher');
		
		CacheFactory.clearAll();
	});

	it("should exist", function () {
		expect(historyService).to.exist;
	});

	describe('getLists()', function () {
		it("should issue a GET /api/history/ request", function () {
			$httpBackend.expect('GET', '/api/history/').respond(200, {});
			historyService.getHistory().then(function (data) {
				expect(data).to.exist;
			});
			$httpBackend.flush();
		});

		it("should report an error if request fails", function () {
			$httpBackend.expect('GET', '/api/history/').respond(500, {
				message: "Request failed"
			});
			historyService.getHistory().catch(function (error) {
				expect(error.data.message).to.equal("Request failed");
				expect(exception.catcher).to.have.been.calledOnce;
			});
			$httpBackend.flush();
		});
	});
});