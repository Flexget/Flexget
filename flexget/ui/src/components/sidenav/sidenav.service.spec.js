/* global bard */
describe('Sidenav Service:', function () {
    beforeEach(function () {
        bard.appModule('components.sidenav');

        /* global sideNavService */
        bard.inject('sideNavService');
    });

    it('should exist', function () {
        expect(sideNavService).to.exist;
    });

    describe('toggle()', function () {
        it('should exist', function () {
            expect(sideNavService.toggle).to.exist;
        });

        //TODO: test funcionalities, check how to mock $mdMedia and $mdSidenav etc
    });

    describe('close()', function () {
        it('should exist', function () {
            expect(sideNavService.close).to.exist;
        });

        //TODO: test funcionalities, check how to mock $mdMedia and $mdSidenav etc
    });
});