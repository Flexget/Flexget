/* global bard, sinon */
describe('Service: Execute', function () {
    beforeEach(function () {
        bard.appModule('plugins.execute');

        /* global $httpBackend, executeService, exception, $q */
        bard.inject('$httpBackend', 'executeService', 'exception', '$q');

        sinon.stub(exception, 'catcher').returns($q.reject({ message: 'Request failed' }));
    });

    it('should exist', function () {
        expect(executeService).to.exist;
    });

    describe('getTasks()', function () {
        it('should issue a GET /api/tasks/ request', function () {
            $httpBackend.expect('GET', '/api/tasks/').respond(200, {});
            executeService.getTasks().then(function (data) {
                expect(data).to.exist;
            });
            $httpBackend.flush();
        });

        it('should report an error if request fails', function () {
            $httpBackend.expect('GET', '/api/tasks/').respond(500);
            executeService.getTasks().catch(function (error) {
                expect(error.message).to.equal('Request failed');
                expect(exception.catcher).to.have.been.calledOnce;
            });
            $httpBackend.flush();
        });
    });

    describe('getQueue()', function () {
        it('should issue a GET /api/tasks/queue/ request', function () {
            $httpBackend.expect('GET', '/api/tasks/queue/').respond(200, {});
            executeService.getQueue().then(function (data) {
                expect(data).to.exist;
            });
            $httpBackend.flush();
        });

        it('should report an error if request fails', function () {
            $httpBackend.expect('GET', '/api/tasks/queue/').respond(500);
            executeService.getQueue().catch(function (error) {
                expect(error.message).to.equal('Request failed');
                expect(exception.catcher).to.have.been.calledOnce;
            });
            $httpBackend.flush();
        });
    });

    describe('executeTasks()', function () {
        //TODO: Test streaming functions
    });
});