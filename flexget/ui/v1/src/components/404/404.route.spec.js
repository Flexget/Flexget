/* global bard */
describe('404 Routes: ', function () {

    beforeEach(function () {
        module('components.404');

        /* global $state, $rootScope, $location */
        bard.inject('$state', '$rootScope', '$location');
    });

    it('should map state \'flexget.404\' to url #/', function () {
        expect($state.href('404', {})).to.equal('#/404');
    });

    it('should map state route to the \'notFound\' component', function () {
        expect($state.get('404').component).to.equal('notFound');
    });

    describe('Transitions', function () {
        it('should work with $state.go', function () {
            $state.go('404');
            $rootScope.$digest();
            expect($state.is('404')).to.be.true;
        });

        it('should work with \'/404\' path', function () {
            $location.path('/404');
            $rootScope.$digest();
            expect($state.is('404')).to.be.true;
        });

        it('should work with \'/unkown\' path', function () {
            $location.path('/unkown');
            $rootScope.$digest();
            expect($state.is('404')).to.be.true;
        });
    });
});