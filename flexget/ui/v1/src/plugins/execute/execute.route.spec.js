/* global bard */
describe('Execute Routes:', function () {

    beforeEach(function () {
        //Create abstract parent state first
        //TODO: create funcion for this, so we can just call the function and not need to inject the entire block everywhere
        module('ui.router', function ($stateProvider) {
            $stateProvider.state('flexget', { abstract: true });
        });
        module('plugins.execute');

        /* global $state, $rootScope, $location */
        bard.inject('$state', '$rootScope', '$location');
    });

    it('should map state \'flexget.execute\' to url #/execute', function () {
        expect($state.href('flexget.execute', {})).to.equal('#/execute');
    });

    it.skip('should map state to the \'execute\' component', function () {
        expect($state.get('flexget.execute').component).to.equal('executeView');
    });

    describe('Transitions', function() {
        it('should work with $state.go', function () {
            $state.go('flexget.execute');
            $rootScope.$digest();
            expect($state.is('flexget.execute')).to.be.true;
        });

        it('should work with \'execute\' path', function() {
            $location.path('execute');
            $rootScope.$digest();
            expect($state.is('flexget.execute')).to.be.true;
        });
    });
});