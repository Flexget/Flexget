describe("Service: Seen", function () {
	beforeEach(function () {
		bard.appModule('plugins.seen');

		bard.inject('$httpBackend', 'seenService', 'exception', 'CacheFactory');

		sinon.stub(exception, 'catcher');
		
		CacheFactory.clearAll();
	});

	it("should exist", function () {
		expect(seenService).to.exist;
	});

	describe('getLists()', function () {
		it("should issue a GET /api/seen/ request", function () {
			$httpBackend.expect('GET', '/api/seen/').respond(200, {});
			seenService.getSeen().then(function (data) {
				expect(data).to.exist;
			});
			$httpBackend.flush();
		});

		it("should report an error if request fails", function () {
			$httpBackend.expect('GET', '/api/seen/').respond(500, {
				message: "Request failed"
			});
			seenService.getSeen().catch(function (error) {
				expect(error.data.message).to.equal("Request failed");
				expect(exception.catcher).to.have.been.calledOnce;
			});
			$httpBackend.flush();
		});
	});
});