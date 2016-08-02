/* global bard */
describe('History Routes:', function () {

    beforeEach(function () {
        //Create abstract parent state first
        //TODO: create funcion for this, so we can just call the function and not need to inject the entire block everywhere
        module('ui.router', function ($stateProvider) {
            $stateProvider.state('flexget', { abstract: true });
        });
        module('plugins.history');

        /* global $state, $rootScope, $location */
        bard.inject('$state', '$rootScope', '$location');
    });

    it('should map state \'flexget.history\' to url #/history', function () {
        expect($state.href('flexget.history', {})).to.equal('#/history');
    });

    it.skip('should map state to the \'history\' component', function () {
        expect($state.get('flexget.history').component).to.equal('historyView');
    });

    describe('Transitions', function () {
        it('should work with $state.go', function () {
            $state.go('flexget.history');
            $rootScope.$digest();
            expect($state.is('flexget.history')).to.be.true;
        });

        it('should work with \'history\' path', function () {
            $location.path('history');
            $rootScope.$digest();
            expect($state.is('flexget.history')).to.be.true;
        });
    });
});