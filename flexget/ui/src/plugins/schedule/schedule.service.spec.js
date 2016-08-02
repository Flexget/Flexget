/* global bard, sinon */
describe('Service: Schedule', function () {
    beforeEach(function () {
        bard.appModule('plugins.schedule');

        /* global $httpBackend, schedulesService, exception, CacheFactory, $q*/
        bard.inject('$httpBackend', 'schedulesService', 'exception', 'CacheFactory', '$q');

        sinon.stub(exception, 'catcher').returns($q.reject({ message: 'Request failed' }));

        CacheFactory.clearAll();
    });

    it('should exist', function () {
        expect(schedulesService).to.exist;
    });

    describe('getLists()', function () {
        it('should issue a GET /api/schedules/ request', function () {
            $httpBackend.expect('GET', '/api/schedules/').respond(200, {});
            schedulesService.getSchedules().then(function (data) {
                expect(data).to.exist;
            });
            $httpBackend.flush();
        });

        it('should report an error if request fails', function () {
            $httpBackend.expect('GET', '/api/schedules/').respond(500);
            schedulesService.getSchedules().catch(function (error) {
                expect(error.message).to.equal('Request failed');
                expect(exception.catcher).to.have.been.calledOnce;
            });
            $httpBackend.flush();
        });
    });
});