/* global bard */
describe('Home Routes: ', function () {

    beforeEach(function () {
        //Create abstract parent state first
        //TODO: create funcion for this, so we can just call the function and not need to inject the entire block everywhere
        module('ui.router', function ($stateProvider) {
            $stateProvider.state('flexget', { abstract: true });
        });
        module('components.home');

        /* global $state, $rootScope, $location */
        bard.inject('$state', '$rootScope', '$location');
    });

    it('should map state \'flexget.home\' to url #/', function () {
        expect($state.href('flexget.home', {})).to.equal('#/');
    });

    it.skip('should map state to the \'home\' component', function () {
        expect($state.get('flexget.home').component).to.equal('home');
    });

    describe('Transitions', function() {
        it('should work with $state.go', function () {
            $state.go('flexget.home');
            $rootScope.$digest();
            expect($state.is('flexget.home')).to.be.true;
        });
    });
});