/* global bard */
describe('Seen Routes:', function () {

    beforeEach(function () {
        //Create abstract parent state first
        //TODO: create funcion for this, so we can just call the function and not need to inject the entire block everywhere
        module('ui.router', function ($stateProvider) {
            $stateProvider.state('flexget', { abstract: true });
        });
        module('plugins.seen');

        /* global $state, $rootScope, $location */
        bard.inject('$state', '$rootScope', '$location');
    });

    it('should map state \'flexget.seen\' to url #/seen', function () {
        expect($state.href('flexget.seen', {})).to.equal('#/seen');
    });

    it.skip('should map state to the \'seen\' component', function () {
        expect($state.get('flexget.seen').component).to.equal('seenView');
    });

    describe('Transitions', function() {
        it('should work with $state.go', function () {
            $state.go('flexget.seen');
            $rootScope.$digest();
            expect($state.is('flexget.seen')).to.be.true;
        });

        it('should work with \'seen\' path', function() {
            $location.path('seen');
            $rootScope.$digest();
            expect($state.is('flexget.seen')).to.be.true;
        });
    });
});