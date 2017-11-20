/* global bard, sinon */
describe('404 Component:', function () {
    var component;

    beforeEach(function () {
        bard.appModule('components.404');

        /* global $state, $componentController */
        bard.inject('$state', '$componentController');
        $state.go = sinon.spy();
    });

    beforeEach(function () {
        component = $componentController('notFound');
    });

    it('should exist', function () {
        expect(component).to.exist;
    });

    describe('goHome()', function () {
        it('should exist', function () {
            expect(component.goHome).to.exist;
        });

        it('should trigger a reroute to home', function () {
            component.goHome();

            expect($state.go).to.have.been.calledOnce;
            expect($state.go).to.have.been.calledWith('flexget.home');
        });
    });
});