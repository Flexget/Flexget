/* global bard */
describe('Series Routes:', function () {

    beforeEach(function () {
        //Create abstract parent state first
        //TODO: create funcion for this, so we can just call the function and not need to inject the entire block everywhere
        module('ui.router', function ($stateProvider) {
            $stateProvider.state('flexget', { abstract: true });
        });
        module('plugins.series');

        /* global $state, $rootScope, $location */
        bard.inject('$state', '$rootScope', '$location');
    });

    it('should map state \'flexget.series\' to url #/series', function () {
        expect($state.href('flexget.series', {})).to.equal('#/series');
    });

    it.skip('should map state to the \'series\' component', function () {
        expect($state.get('flexget.series').component).to.equal('seriesView');
    });

    describe('Transitions', function() {
        it('should work with $state.go', function () {
            $state.go('flexget.series');
            $rootScope.$digest();
            expect($state.is('flexget.series')).to.be.true;
        });

        it('should work with \'series\' path', function() {
            $location.path('series');
            $rootScope.$digest();
            expect($state.is('flexget.series')).to.be.true;
        });
    });
});