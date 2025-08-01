/* global bard */
describe('Schedule Routes:', function () {
  beforeEach(function () {
    //Create abstract parent state first
    //TODO: create funcion for this, so we can just call the function and not need to inject the entire block everywhere
    module('ui.router', function ($stateProvider) {
      $stateProvider.state('flexget', { abstract: true });
    });
    module('plugins.schedule');

    /* global $state, $rootScope, $location */
    bard.inject('$state', '$rootScope', '$location');
  });

  it("should map state 'flexget.schedule' to url #/schedule", function () {
    expect($state.href('flexget.schedule', {})).to.equal('#/schedule');
  });

  it.skip("should map state to the 'schedule' component", function () {
    expect($state.get('flexget.schedule').component).to.equal('scheduleView');
  });

  describe('Transitions', function () {
    it('should work with $state.go', function () {
      $state.go('flexget.schedule');
      $rootScope.$digest();
      expect($state.is('flexget.schedule')).to.be.true;
    });

    it("should work with 'schedule' path", function () {
      $location.path('schedule');
      $rootScope.$digest();
      expect($state.is('flexget.schedule')).to.be.true;
    });
  });
});
