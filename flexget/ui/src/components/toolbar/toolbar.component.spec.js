/* global bard, sinon */
describe('Toolbar Component:', function () {
    var component;

    beforeEach(function () {
        bard.appModule('components.toolbar');

        /* global $componentController, sideNavService */
        bard.inject('$componentController', 'sideNavService');

        sinon.stub(sideNavService, 'toggle');
    });

    beforeEach(function () {
        component = $componentController('toolBar');
    });

    it('should exist', function () {
        expect(component).to.exist;
    });

    describe('activation', function () {
        beforeEach(function () {
            component.$onInit();
        });

        it('should have items', function () {
            expect(component.toolBarItems).to.exist;
            expect(component.toolBarItems).to.have.length.above(0);
        });
    });

    describe('toggle', function () {
        it('should exist', function () {
            expect(component.toggle).to.exist;
        });

        it('should call the sideNav toggle function', function () {
            component.toggle();

            expect(sideNavService.toggle).to.have.been.calledOnce;
        });
    });
});