/* global bard */
describe('Config Routes:', function () {

    beforeEach(function () {
        //Create abstract parent state first
        //TODO: create funcion for this, so we can just call the function and not need to inject the entire block everywhere
        module('ui.router', function ($stateProvider) {
            $stateProvider.state('flexget', { abstract: true });
        });
        module('plugins.config');

        /* global $state, $rootScope, $location */
        bard.inject('$state', '$rootScope', '$location');
    });

    it('should map state \'flexget.config\' to url #/config', function () {
        expect($state.href('flexget.config', {})).to.equal('#/config');
    });

    it.skip('should map state to the \'config\' component', function () {
        expect($state.get('flexget.config').component).to.equal('configView');
    });

    describe('Transitions', function() {
        it('should work with $state.go', function () {
            $state.go('flexget.config');
            $rootScope.$digest();
            expect($state.is('flexget.config')).to.be.true;
        });

        it('should work with \'config\' path', function() {
            $location.path('config');
            $rootScope.$digest();
            expect($state.is('flexget.config')).to.be.true;
        });
    });
});