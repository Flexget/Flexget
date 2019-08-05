/* global bard, sinon */
describe('Service: Movies', function () {
    beforeEach(function () {
        bard.appModule('plugins.movies');

        /* global $httpBackend, moviesService, exception, $q */
        bard.inject('$httpBackend', 'moviesService', 'exception', '$q');

        sinon.stub(exception, 'catcher').returns($q.reject({ message: 'Request failed' }));
    });

    it('should exist', function () {
        expect(moviesService).to.exist;
    });

    describe('getLists()', function () {
        it('should issue a GET /api/movie_list/ request', function () {
            $httpBackend.expect('GET', '/api/movie_list/').respond(200, {});
            moviesService.getLists().then(function (data) {
                expect(data).to.exist;
            });
            $httpBackend.flush();
        });

        it('should report an error if request fails', function () {
            $httpBackend.expect('GET', '/api/movie_list/').respond(500);
            moviesService.getLists().catch(function (error) {
                expect(error.message).to.equal('Request failed');
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

        it('should report an error if request fails', function () {
            $httpBackend.expect('DELETE', '/api/movie_list/1/').respond(500);
            moviesService.deleteList(1).catch(function (error) {
                expect(error.message).to.equal('Request failed');
                expect(exception.catcher).to.have.been.calledOnce;
            });
            $httpBackend.flush();
        });
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
            $httpBackend.expect('GET', '/api/movie_list/1/movies/').respond(500);
            moviesService.getListMovies(1).catch(function (error) {
                expect(error.message).to.equal('Request failed');
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
            $httpBackend.expect('DELETE', '/api/movie_list/1/movies/1/').respond(500);
            moviesService.deleteMovie(1, 1).catch(function (error) {
                expect(error.message).to.equal('Request failed');
                expect(exception.catcher).to.have.been.calledOnce;
            });
            $httpBackend.flush();
        });
    });

    describe('createList()', function () {
        it('should issue a POST /api/movie_list/ request', function () {
            $httpBackend.expect('POST', '/api/movie_list/').respond(200, {});
            moviesService.createList('New List').then(function (data) {
                expect(data).to.exist;
            });
            $httpBackend.flush();
        });

        it('should report an error if request fails', function () {
            $httpBackend.expect('POST', '/api/movie_list/').respond(500);
            moviesService.createList('New List').catch(function (error) {
                expect(error.message).to.equal('Request failed');
                expect(exception.catcher).to.have.been.calledOnce;
            });
            $httpBackend.flush();
        });
    });

    describe('getMovieMetadata()', function () {
        it('should issue a GET /api/trakt/movies/:title/ request', function () {
            $httpBackend.expect('GET', '/api/trakt/movies/Warcraft/').respond(200, {});
            moviesService.getMovieMetadata('Warcraft').then(function (data) {
                expect(data).to.exist;
            });
            $httpBackend.flush();
        });

        it('should report an error if request fails', function () {
            $httpBackend.expect('GET', '/api/trakt/movies/Warcraft/').respond(500);
            moviesService.getMovieMetadata('Warcraft').catch(function (error) {
                expect(error.message).to.equal('Request failed');
                expect(exception.catcher).to.have.been.calledOnce;
            });
            $httpBackend.flush();
        });
    });
});