/* global bard, sinon */
describe('Login Config: ', function () {
    var httpProvider;
    beforeEach(function () {
        bard.appModule('components.auth',
            function ($httpProvider) {
                httpProvider = $httpProvider;
            });

        /* global authInterceptor, authService, $rootScope */
        bard.inject('authInterceptor', 'authService', '$rootScope');
    });

    it('should exist', function () {
        expect(authInterceptor).to.exist;
    });

    describe('config', function () {
        it('should add the authInterceptor to the list of interceptors', function () {
            expect(httpProvider.interceptors).to.contain('authInterceptor');
        });
    });

    describe('responseError()', function () {
        beforeEach(function () {
            sinon.stub(authService, 'state');
            sinon.stub($rootScope, '$broadcast');
        });

        it('should exist', function () {
            expect(authInterceptor.responseError).to.exist;
            expect(authInterceptor.responseError).to.be.a('function');
        });

        it('should broadcast an event on auth error', function () {
            var rejection = {
                status: 401,
                config: {}
            };

            authInterceptor.responseError(rejection);

            expect($rootScope.$broadcast).to.have.been.calledOnce;
            expect($rootScope.$broadcast).to.have.been.calledWith('event:auth-loginRequired', true);
        });

        it('should not broadcast when ignoreAuthModule is true', function () {
            var rejection = {
                status: 401,
                config: {
                    ignoreAuthModule: true
                }
            };

            authInterceptor.responseError(rejection);

            expect($rootScope.$broadcast).not.to.have.been.called;
        });
    });
});