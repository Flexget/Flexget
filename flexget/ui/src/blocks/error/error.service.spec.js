/* global bard, sinon */
describe('Blocks: Error', function () {
    describe('Error.service', function () {
        beforeEach(function () {
            bard.appModule('blocks.error');

            /* global errorService, $mdToast */
            bard.inject('errorService', '$mdToast');
        });

        it('should exist', function () {
            expect(errorService).to.exist;
        });

        describe('showToast()', function () {
            it('should show toast', function () {
                sinon.spy($mdToast, 'show');

                errorService.showToast();

                expect($mdToast.show).to.have.been.calledOnce;
            });
        });
    });
});