/* global bard */
describe('Log Routes:', function () {

    beforeEach(function () {
        //Create abstract parent state first
        //TODO: create funcion for this, so we can just call the function and not need to inject the entire block everywhere
        module('ui.router', function ($stateProvider) {
            $stateProvider.state('flexget', { abstract: true });
        });
        module('plugins.log');

        /* global $state, $rootScope, $location */
        bard.inject('$state', '$rootScope', '$location');
    });

    it('should map state \'flexget.log\' to url #/log', function () {
        expect($state.href('flexget.log', {})).to.equal('#/log');
    });

    it.skip('should map state to the \'log\' component', function () {
        expect($state.get('flexget.log').component).to.equal('logView');
    });

    describe('Transitions', function() {
        it('should work with $state.go', function () {
            $state.go('flexget.log');
            $rootScope.$digest();
            expect($state.is('flexget.log')).to.be.true;
        });

        it('should work with \'log\' path', function() {
            $location.path('log');
            $rootScope.$digest();
            expect($state.is('flexget.log')).to.be.true;
        });
    });
});