/* global bard */
describe('Core Routes:', function () {
    beforeEach(function () {
		module('components.core');

		/* global $state, $rootScope, $location */
		bard.inject('$state', '$rootScope', '$location');
    });

    it('Abstract parent state \'flexget\' should be present in all states', function () {
		expect($state.get('flexget').name).to.equal('flexget');
		expect($state.get('flexget').abstract).to.be.true;
		expect($state.get('flexget').templateUrl).to.equal('layout.tmpl.html');
    });
});