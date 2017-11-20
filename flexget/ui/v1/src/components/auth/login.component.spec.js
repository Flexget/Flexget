/* global bard, sinon */
describe('Login Component:', function () {
    var component, deferred;

    beforeEach(function () {
        bard.appModule('components.auth');

        /* global $componentController, authService, $q, $rootScope */
        bard.inject('$componentController', 'authService', '$q', '$rootScope');
    });

    beforeEach(function () {
        component = $componentController('login');
    });

    it('should exist', function () {
        expect(component).to.exist;
    });

    describe('login()', function () {
        beforeEach(function () {
            deferred = $q.defer();

            sinon.stub(authService, 'login').returns(deferred.promise);
        });
        it('should exist', function () {
            expect(component.login).to.exist;
        });

        it('should set the error variable to the error message when present', function () {
            deferred.reject({
                'message': 'Invalid username or password',
                'status': 'failed'
            });

            component.login();

            $rootScope.$digest();

            expect(component.error).to.equal('Invalid username or password');
        });

        it('should set the error message to a general message when none is present', function () {
            deferred.reject({});

            component.login();

            $rootScope.$digest();

            expect(component.error).to.equal('Error during authentication');
        });

        it('should empty the password when the login fails', function () {
            deferred.reject({});

            component.credentials = {
                password: 'Testing'
            };

            component.login();

            $rootScope.$digest();

            expect(component.credentials.password).to.equal('');
        });
    });
});