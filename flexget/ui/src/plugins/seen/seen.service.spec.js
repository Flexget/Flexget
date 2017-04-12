/* global bard, sinon */
describe('Service: Seen', function () {
    beforeEach(function () {
        bard.appModule('plugins.seen');

        /* global $httpBackend, seenService, exception, $q */
        bard.inject('$httpBackend', 'seenService', 'exception', '$q');

        sinon.stub(exception, 'catcher').returns($q.reject({ message: 'Request failed' }));
    });

    it('should exist', function () {
        expect(seenService).to.exist;
    });

    describe('getLists()', function () {
        it('should issue a GET /api/seen/ request', function () {
            $httpBackend.expect('GET', '/api/seen/').respond(200, {});
            seenService.getSeen().then(function (data) {
                expect(data).to.exist;
            });
            $httpBackend.flush();
        });

        it('should report an error if request fails', function () {
            $httpBackend.expect('GET', '/api/seen/').respond(500);
            seenService.getSeen().catch(function (error) {
                expect(error.message).to.equal('Request failed');
                expect(exception.catcher).to.have.been.calledOnce;
            });
            $httpBackend.flush();
        });
    });
});