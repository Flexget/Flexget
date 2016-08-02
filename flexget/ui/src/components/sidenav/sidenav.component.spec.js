/* global bard, sinon, mockStatesData */
describe('Sidenav Component:', function () {
    var component;
    var mockStates = mockStatesData.getStates();

    beforeEach(function () {
        bard.appModule('components.sidenav');

        /* global $componentController, routerHelper, sideNavService */
        bard.inject('$componentController', 'routerHelper', 'sideNavService');

        sinon.stub(routerHelper, 'getStates').returns(mockStates);
        sinon.stub(sideNavService, 'close');
    });

    beforeEach(function () {
        component = $componentController('sideNav');
    });

    it('should exist', function () {
        expect(component).to.exist;
    });

    describe('after activation', function () {
        beforeEach(function () {
            component.$onInit();
        });

        it('should have items', function () {
            expect(component.navItems).to.exist;
            expect(component.navItems).to.have.length.above(0);
        });

        it('should filter the sidebar items correctly', function () {
            expect(component.navItems).to.have.length(mockStates.length - 1);
        });
    });

    describe('close()', function() {
        it('should exist', function () {
            expect(component.close).to.exist;
        });

        it('should call the sideNav close function', function () {
            component.close();

            expect(sideNavService.close).to.have.been.calledOnce;
        });
    });
});