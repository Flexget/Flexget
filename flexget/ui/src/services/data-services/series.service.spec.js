describe("Service: Series", function () {
	beforeEach(function () {
		bard.appModule('flexget.services');

		bard.inject('$httpBackend', 'seriesService', 'exception', 'CacheFactory');

		sinon.spy(exception, 'catcher');

		//Clear all caches before the tests to prevent cross test caching
		CacheFactory.clearAll();
	});

	it("should exist", function () {
		expect(seriesService).to.exist;
	});

	describe('getShows()', function () {
		it("should issue a GET /api/series/ request", function () {
			$httpBackend.expect('GET', '/api/series/').respond(200, {});
			seriesService.getShows().then(function (data) {
				expect(data).to.exist;
			});
			$httpBackend.flush();
		});

		it("should report an error if request fails", function () {
			$httpBackend.expect('GET', '/api/series/').respond(500, {
				message: "Request failed"
			});
			seriesService.getShows().catch(function (error) {
				expect(error.data.message).to.equal("Request failed");
				expect(exception.catcher).to.have.been.calledOnce;
			});
			$httpBackend.flush();
		});

		//TODO: Figure out how to test the caching system	

		/*	it("should only call the API only once because of caching", function () {
				$httpBackend.expect('GET', '/api/series/').respond(200, JSON.stringify({}));
				seriesService.getShows().then(function (data) {
					console.log(data);
					expect(data).to.exist;
				});
				$httpBackend.flush();
	
				//CacheFactory.clearAll();
	
				$httpBackend.resetExpectations();			
	
				$httpBackend.expect('GET', '/api/series/').respond(200, JSON.stringify({}));
				
				
				seriesService.getShows().then(function (data) {
					console.log(data);
					expect(data).to.exist;
					//expect(true).to.be.false;
				});
				$httpBackend.flush();
			});*/
	});

	describe('deleteShow()', function () {
		it("should issue a DELETE /api/series/1 request", function () {
			$httpBackend.expect('DELETE', '/api/series/1?forget=true').respond(200, {});
			seriesService.deleteShow({ show_id: 1 }).then(function (data) {
				expect(data).not.to.exist;
			});
			$httpBackend.flush();
		});

		it("should report an error if request fails", function () {
			$httpBackend.expect('DELETE', '/api/series/1?forget=true').respond(500, {
				message: "Request failed"
			});
			seriesService.deleteShow({ show_id: 1 }).catch(function (error) {
				expect(error.data.message).to.equal("Request failed");
				expect(exception.catcher).to.have.been.calledOnce;
			});
			$httpBackend.flush();
		});
	});

	describe('searchShows()', function () {
		it("should issue a GET /api/series/search/iZombie request", function () {
			$httpBackend.expect('GET', '/api/series/search/iZombie').respond(200, {});
			seriesService.searchShows("iZombie").then(function (data) {
				expect(data).to.exist;
			});
			$httpBackend.flush();
		});

		it("should report an error if request fails", function () {
			$httpBackend.expect('GET', '/api/series/search/iZombie').respond(500, {
				message: "Request failed"
			});
			seriesService.searchShows("iZombie").catch(function (error) {
				expect(error.data.message).to.equal("Request failed");
				expect(exception.catcher).to.have.been.calledOnce;
			});
			$httpBackend.flush();
		});

		//TODO: Test search result

	});
});