describe("Service: Movies", function () {
	beforeEach(function () {
		bard.appModule('flexget.services');
		
		bard.inject('$httpBackend', 'moviesService', 'exception');

		sinon.spy(exception, 'catcher');
	});

	it("should exist", function () {
		expect(moviesService).to.exist;
	});

	describe('getLists()', function () {
		it("should hit the /api/movie_list/ endpoint", function () {
			$httpBackend.when('GET', '/api/movie_list/').respond(200, [{}]);
			moviesService.getLists().then(function (data) {
				expect(data).to.exist;
			});
			$httpBackend.flush();
		});

		it("should report an error if request fails", function () {
			$httpBackend.when('GET', '/api/movie_list/').respond(500, {
				message: "Request failed"
			});
			moviesService.getLists().catch(function (error) {
				expect(error.data.message).to.equal("Request failed");
				expect(exception.catcher).to.have.been.calledOnce;
			});
			$httpBackend.flush();
		});
	});
});