/* global bard, sinon */
describe('Service: Auth', function () {
    beforeEach(function () {
        bard.appModule('components.auth');

        /* global $httpBackend, authService, exception, $q, $state */
        bard.inject('$httpBackend', 'authService', 'exception', '$q', '$state');

        sinon.stub(exception, 'catcher').returns($q.reject({ message: 'Request failed' }));

        $state.go = sinon.stub();
    });

    it('should exist', function () {
        expect(authService).to.exist;
    });

    describe('logout()', function () {
        it('should issue a GET /api/auth/logout/ request', function () {
            $httpBackend.expect('GET', '/api/auth/logout/').respond(200, {});

            authService.logout();

            $httpBackend.flush();
            $httpBackend.verifyNoOutstandingExpectation();
            $httpBackend.verifyNoOutstandingRequest();
        });

        describe('successful logout', function () {
            beforeEach(function () {
                $httpBackend.expect('GET', '/api/auth/logout/').respond(200, {});

                authService.logout();
            });

            it('should go to the login state after successful logout', function () {
                $httpBackend.flush();

                expect($state.go).to.have.been.calledOnce;
                expect($state.go).to.have.been.calledWith('login');
            });

            it('should go to home page after new login', function () {
                authService.state({ name: 'flexget.history' });

                $httpBackend.flush();

                $httpBackend.expect('POST', '/api/auth/login/?remember=false').respond(200, {});

                $state.go.reset();

                authService.login();

                $httpBackend.flush();

                expect($state.go).to.have.been.calledOnce;
                expect($state.go).to.have.been.calledWith('flexget.home');
            });
        });

        it('should report an error if request fails', function () {
            $httpBackend.expect('GET', '/api/auth/logout/').respond(500);
            authService.logout().catch(function (error) {
                expect(error.message).to.equal('Request failed');
                expect(exception.catcher).to.have.been.calledOnce;
            });
            $httpBackend.flush();
        });
    });

    describe('login()', function () {
        it('should issue a POST /api/auth/login/ request', function () {
            $httpBackend.expect('POST', '/api/auth/login/?remember=false').respond(200, {});

            authService.login();

            $httpBackend.flush();
            $httpBackend.verifyNoOutstandingExpectation();
            $httpBackend.verifyNoOutstandingRequest();
        });

        describe('after successful login', function () {
            beforeEach(function () {
                $httpBackend.expect('POST', '/api/auth/login/?remember=false').respond(200, {});

                authService.login();
            });

            it('should go to the home state when no state is defined', function () {
                $httpBackend.flush();

                expect($state.go).to.have.been.calledOnce;
                expect($state.go).to.have.been.calledWith('flexget.home');
            });

            it('should go to the previously saved state', function () {
                authService.state({ name: 'flexget.history' });

                $httpBackend.flush();

                expect($state.go).to.have.been.calledOnce;
                expect($state.go).to.have.been.calledWith('flexget.history');
            });
        });

        it('should reject when an error occurs', function () {
            $httpBackend.expect('POST', '/api/auth/login/?remember=false').respond(500, {});

            authService.login().catch(function (data) {
                expect(data).to.exist;
            });
            $httpBackend.flush();
        });
    });
});