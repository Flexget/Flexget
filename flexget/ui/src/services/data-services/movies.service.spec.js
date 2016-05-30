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
		it("should issue a GET /api/movie_list/ request", function () {
			$httpBackend.expect('GET', '/api/movie_list/').respond(200, {});
			moviesService.getLists().then(function (data) {
				expect(data).to.exist;
			});
			$httpBackend.flush();
		});

		it("should report an error if request fails", function () {
			$httpBackend.expect('GET', '/api/movie_list/').respond(500, {
				message: "Request failed"
			});
			moviesService.getLists().catch(function (error) {
				expect(error.data.message).to.equal("Request failed");
				expect(exception.catcher).to.have.been.calledOnce;
			});
			$httpBackend.flush();
		});
	});

	describe('deleteList()', function () {
		it('should issue a DELETE /api/movie_list/:id/ request', function () {
			$httpBackend.expect('DELETE', '/api/movie_list/1/').respond(200, {});
			moviesService.deleteList(1).then(function (data) {
				expect(data).not.to.exist;
			});
			$httpBackend.flush();
		});

		it("should report an error if request fails", function () {
			$httpBackend.expect('DELETE', '/api/movie_list/1/').respond(500, {
				message: "Request failed"
			});
			moviesService.deleteList(1).catch(function (error) {
				expect(error.data.message).to.equal("Request failed");
				expect(exception.catcher).to.have.been.calledOnce;
			});
			$httpBackend.flush();
		})
	});

	describe('getListMovies()', function () {
		it('should issue a GET /api/movie_list/:id/movies/ request', function () {
			$httpBackend.expect('GET', '/api/movie_list/1/movies/').respond(200, {});
			moviesService.getListMovies(1).then(function (data) {
				expect(data).to.exist;
			});
			$httpBackend.flush();
		});

		it('should report an error if request fails', function () {
			$httpBackend.expect('GET', '/api/movie_list/1/movies/').respond(500, {
				message: "Request failed"
			});
			moviesService.getListMovies(1).catch(function (error) {
				expect(error.data.message).to.equal("Request failed");
				expect(exception.catcher).to.have.been.calledOnce;
			});
			$httpBackend.flush();
		});
	});

	describe('deleteMovie()', function () {
		it('should issue a DELETE /api/movie_list/:lid/movies/:mid/ request', function () {
			$httpBackend.expect('DELETE', '/api/movie_list/1/movies/1/').respond(200, {});
			moviesService.deleteMovie(1, 1).then(function (data) {
				expect(data).not.to.exist;
			});
			$httpBackend.flush();
		});

		it('should report an error if request fails', function () {
			$httpBackend.expect('DELETE', '/api/movie_list/1/movies/1/').respond(500, {
				message: "Request failed"
			});
			moviesService.deleteMovie(1, 1).catch(function (error) {
				expect(error.data.message).to.equal("Request failed");
				expect(exception.catcher).to.have.been.calledOnce;
			});
			$httpBackend.flush();
		});
	});

	describe('createList()', function () {
		it('should issue a POST /api/movie_list/ request', function () {
			$httpBackend.expect('POST', '/api/movie_list/').respond(200, {});
			moviesService.createList("New List").then(function (data) {
				expect(data).to.exist;
			});
			$httpBackend.flush();
		});

		it('should report an error if request fails', function () {
			$httpBackend.expect('POST', '/api/movie_list/').respond(500, {
				message: "Request failed"
			});
			moviesService.createList("New List").catch(function (error) {
				expect(error.data.message).to.equal("Request failed");
				expect(exception.catcher).to.have.been.calledOnce;
			});
			$httpBackend.flush();
		});
	});
});