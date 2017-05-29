/* global bard */
describe('Movies Routes:', function () {

    beforeEach(function () {
        //Create abstract parent state first
        //TODO: create funcion for this, so we can just call the function and not need to inject the entire block everywhere
        module('ui.router', function ($stateProvider) {
            $stateProvider.state('flexget', { abstract: true });
        });
        module('plugins.movies');

        /* global $state, $rootScope, $location */
        bard.inject('$state', '$rootScope', '$location');
    });

    it('should map state \'flexget.movies\' to url #/movies', function () {
        expect($state.href('flexget.movies', {})).to.equal('#/movies');
    });

    it.skip('should map state to the \'movies\' component', function () {
        expect($state.get('flexget.movies').component).to.equal('moviesView');
    });

    describe('Transitions', function() {
        it('should work with $state.go', function () {
            $state.go('flexget.movies');
            $rootScope.$digest();
            expect($state.is('flexget.movies')).to.be.true;
        });

        it('should work with \'movies\' path', function() {
            $location.path('movies');
            $rootScope.$digest();
            expect($state.is('flexget.movies')).to.be.true;
        });
    });
});