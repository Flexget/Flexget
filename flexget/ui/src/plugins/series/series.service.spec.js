/* global bard, sinon */
describe('Service: Series', function () {
    beforeEach(function () {
        bard.appModule('plugins.series');

        /* global $httpBackend, seriesService, exception, CacheFactory, $q */
        bard.inject('$httpBackend', 'seriesService', 'exception', 'CacheFactory', '$q');

        sinon.stub(exception, 'catcher').returns($q.reject({ message: 'Request failed' }));

        //Clear all caches before the tests to prevent cross test caching
        CacheFactory.clearAll();
    });

    it('should exist', function () {
        expect(seriesService).to.exist;
    });

    describe('getShows()', function () {
        it('should issue a GET /api/series/ request', function () {
            $httpBackend.expect('GET', '/api/series/').respond(200, {});
            seriesService.getShows().then(function (data) {
                expect(data).to.exist;
            });
            $httpBackend.flush();
        });

        it('should report an error if request fails', function () {
            $httpBackend.expect('GET', '/api/series/').respond(500);
            seriesService.getShows().catch(function (error) {
                expect(error.message).to.equal('Request failed');
                expect(exception.catcher).to.have.been.calledOnce;
            });
            $httpBackend.flush();
        });

        //TODO: Figure out how to test the caching system

        /*  it("should only call the API only once because of caching", function () {
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

    describe('getShowMetadata()', function () {
        it('should issue a GET /api/tvdb/series/:name/ request', function () {
            $httpBackend.expect('GET', '/api/tvdb/series/iZombie/').respond(200, {});
            seriesService.getShowMetadata({ 'show_name': 'iZombie' }).then(function (data) {
                expect(data).to.exist;
            });
            $httpBackend.flush();
        });

        it('should report an error if request fails', function () {
            $httpBackend.expect('GET', '/api/tvdb/series/iZombie/').respond(500);
            seriesService.getShowMetadata({ 'show_name': 'iZombie' }).catch(function (error) {
                expect(error.message).to.equal('Request failed');
                expect(exception.catcher).to.have.been.calledOnce;
            });
            $httpBackend.flush();
        });
    });

    describe('deleteShow()', function () {
        it('should issue a DELETE /api/series/:id/ request', function () {
            $httpBackend.expect('DELETE', '/api/series/1/').respond(200, {});
            seriesService.deleteShow({ 'show_id': 1 }).then(function (data) {
                expect(data).not.to.exist;
            });
            $httpBackend.flush();
        });

        it('should report an error if request fails', function () {
            $httpBackend.expect('DELETE', '/api/series/1/').respond(500);
            seriesService.deleteShow({ 'show_id': 1 }).catch(function (error) {
                expect(error.message).to.equal('Request failed');
                expect(exception.catcher).to.have.been.calledOnce;
            });
            $httpBackend.flush();
        });
    });

    describe('searchShows()', function () {
        it('should issue a GET /api/series/search/:term/ request', function () {
            $httpBackend.expect('GET', '/api/series/search/iZombie/').respond(200, {});
            seriesService.searchShows('iZombie').then(function (data) {
                expect(data).to.exist;
            });
            $httpBackend.flush();
        });

        it('should report an error if request fails', function () {
            $httpBackend.expect('GET', '/api/series/search/iZombie/').respond(500);
            seriesService.searchShows('iZombie').catch(function (error) {
                expect(error.message).to.equal('Request failed');
                expect(exception.catcher).to.have.been.calledOnce;
            });
            $httpBackend.flush();
        });

        //TODO: Test search result

    });

    describe('getEpisodes()', function () {
        it('should issue a GET /api/series/:id/episodes/ request', function () {
            $httpBackend.expect('GET', '/api/series/1/episodes/').respond(200, {});
            seriesService.getEpisodes({ 'show_id': 1 }).then(function (data) {
                expect(data).to.exist;
            });
            $httpBackend.flush();
        });

        it('should report an error if request fails', function () {
            $httpBackend.expect('GET', '/api/series/1/episodes/').respond(500);
            seriesService.getEpisodes({ 'show_id': 1 }).catch(function (error) {
                expect(error.message).to.equal('Request failed');
                expect(exception.catcher).to.have.been.calledOnce;
            });
            $httpBackend.flush();
        });
    });

    describe('deleteEpisode()', function () {
        it('should issue a DELETE /api/series/:sid/episodes/:eid/ request', function () {
            $httpBackend.expect('DELETE', '/api/series/1/episodes/1/').respond(200, {});
            seriesService.deleteEpisode({ 'show_id': 1 }, { 'episode_id': 1 }).then(function (data) {
                expect(data).to.exist;
            });
            $httpBackend.flush();
        });

        it('should report an error if request fails', function () {
            $httpBackend.expect('DELETE', '/api/series/1/episodes/1/').respond(500);
            seriesService.deleteEpisode({ 'show_id': 1 }, { 'episode_id': 1 }).catch(function (error) {
                expect(error.message).to.equal('Request failed');
                expect(exception.catcher).to.have.been.calledOnce;
            });
            $httpBackend.flush();
        });
    });

    describe('resetReleases()', function () {
        it('should issue a PUT /api/series/:sid/episodes/:eid/releases/ request', function () {
            $httpBackend.expect('PUT', '/api/series/1/episodes/1/releases/').respond(200, {});
            seriesService.resetReleases({ 'show_id': 1 }, { 'episode_id': 1 }).then(function (data) {
                expect(data).to.exist;
            });
            $httpBackend.flush();
        });

        it('should report an error if request fails', function () {
            $httpBackend.expect('PUT', '/api/series/1/episodes/1/releases/').respond(500);
            seriesService.resetReleases({ 'show_id': 1 }, { 'episode_id': 1 }).catch(function (error) {
                expect(error.message).to.equal('Request failed');
                expect(exception.catcher).to.have.been.calledOnce;
            });
            $httpBackend.flush();
        });
    });

    describe('forgetRelease()', function () {
        it('should issue a DELETE /api/series/:sid/episodes/:eid/releases/:rid/ request', function () {
            $httpBackend.expect('DELETE', '/api/series/1/episodes/1/releases/1/').respond(200, {});
            seriesService.forgetRelease({ 'show_id': 1 }, { 'episode_id': 1 }, { 'release_id': 1 }).then(function (data) {
                expect(data).to.exist;
            });
            $httpBackend.flush();
        });

        it('should report an error if request fails', function () {
            $httpBackend.expect('DELETE', '/api/series/1/episodes/1/releases/1/').respond(500);
            seriesService.forgetRelease({ 'show_id': 1 }, { 'episode_id': 1 }, { 'release_id': 1 }).catch(function (error) {
                expect(error.message).to.equal('Request failed');
                expect(exception.catcher).to.have.been.calledOnce;
            });
            $httpBackend.flush();
        });
    });

    describe('resetRelease()', function () {
        it('should issue a PUT /api/series/:sid/episodes/:eid/releases/:rid/ request', function () {
            $httpBackend.expect('PUT', '/api/series/1/episodes/1/releases/1/').respond(200, {});
            seriesService.resetRelease({ 'show_id': 1 }, { 'episode_id': 1 }, { 'release_id': 1 }).then(function (data) {
                expect(data).to.exist;
            });
            $httpBackend.flush();
        });

        it('should report an error if request fails', function () {
            $httpBackend.expect('PUT', '/api/series/1/episodes/1/releases/1/').respond(500);
            seriesService.resetRelease({ 'show_id': 1 }, { 'episode_id': 1 }, { 'release_id': 1 }).catch(function (error) {
                expect(error.message).to.equal('Request failed');
                expect(exception.catcher).to.have.been.calledOnce;
            });
            $httpBackend.flush();
        });
    });

    describe('deleteReleases()', function () {
        it('should issue a DELETE /api/series/:sid/episodes/:eid/releases/ request', function () {
            $httpBackend.expect('DELETE', '/api/series/1/episodes/1/releases/').respond(200, {});
            seriesService.deleteReleases({ 'show_id': 1 }, { 'episode_id': 1 }).then(function () {
                expect(true).to.be.true;
            });
            $httpBackend.flush();
        });

        it('should report an error if request fails', function () {
            $httpBackend.expect('DELETE', '/api/series/1/episodes/1/releases/').respond(500);
            seriesService.deleteReleases({ 'show_id': 1 }, { 'episode_id': 1 }).catch(function (error) {
                expect(error.message).to.equal('Request failed');
                expect(exception.catcher).to.have.been.calledOnce;
            });
            $httpBackend.flush();
        });
    });

    describe('loadReleases()', function () {
        it('should issue a GET /api/series/:sid/episodes/:eid/releases/ request', function () {
            $httpBackend.expect('GET', '/api/series/1/episodes/1/releases/').respond(200, {});
            seriesService.loadReleases({ 'show_id': 1 }, { 'episode_id': 1 }).then(function (data) {
                expect(data).to.exist;
            });
            $httpBackend.flush();
        });

        it('should report an error if request fails', function () {
            $httpBackend.expect('GET', '/api/series/1/episodes/1/releases/').respond(500);
            seriesService.loadReleases({ 'show_id': 1 }, { 'episode_id': 1 }).catch(function (error) {
                expect(error.message).to.equal('Request failed');
                expect(exception.catcher).to.have.been.calledOnce;
            });
            $httpBackend.flush();
        });
    });
});
