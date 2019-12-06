/* global bard, sinon */
describe('Service: History', function () {
    beforeEach(function () {
        bard.appModule('plugins.history');

        /* global $httpBackend, historyService, exception, CacheFactory, $q */
        bard.inject('$httpBackend', 'historyService', 'exception', 'CacheFactory', '$q');

        sinon.stub(exception, 'catcher').returns($q.reject({ message: 'Request failed' }));

        CacheFactory.clearAll();
    });

    it('should exist', function () {
        expect(historyService).to.exist;
    });

    describe('getLists()', function () {
        it('should issue a GET /api/history/ request', function () {
            $httpBackend.expect('GET', '/api/history/').respond(200, {});
            historyService.getHistory().then(function (data) {
                expect(data).to.exist;
            });
            $httpBackend.flush();
        });

        it('should report an error if request fails', function () {
            $httpBackend.expect('GET', '/api/history/').respond(500);
            historyService.getHistory().catch(function (error) {
                expect(error.message).to.equal('Request failed');
                expect(exception.catcher).to.have.been.calledOnce;
            });
            $httpBackend.flush();
        });
    });
});