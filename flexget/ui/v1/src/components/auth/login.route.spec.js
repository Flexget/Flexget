/* global bard */
describe('Login Routes: ', function () {
    beforeEach(function () {
        module('components.auth');

        /* global $state, $rootScope, $location */
        bard.inject('$state', '$rootScope', '$location');
    });

    it('should map state \'flexget.login\' to url #/login', function () {
        expect($state.href('login', {})).to.equal('#/login');
    });

    it('should map state route to the \'login\' component', function () {
        expect($state.get('login').component).to.equal('login');
    });

    describe('Transitions', function() {
        it('should work with $state.go', function () {
            $state.go('login');
            $rootScope.$digest();
            expect($state.is('login')).to.be.true;
        });

        it('should work with \'/login\' path', function() {
            $location.path('/login');
            $rootScope.$digest();
            expect($state.is('login')).to.be.true;
        });
    });
});