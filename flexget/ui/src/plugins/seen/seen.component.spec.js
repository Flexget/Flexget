/* global bard, sinon, mockSeenData */
describe('Plugin: Seen.component', function () {
    var controller;
    var seen = mockSeenData.getMockSeen();

    beforeEach(function () {
        bard.appModule('plugins.seen');

        /* global $componentController, seenService, $q, $rootScope */
        bard.inject('$componentController', 'seenService', '$q', '$rootScope');

        sinon.stub(seenService, 'getSeen').returns($q.when(seen));
    });

    beforeEach(function () {
        controller = $componentController('seenView');
    });

    it('should exist', function () {
        expect(controller).to.exist;
    });

    describe('activation', function () {
        beforeEach(function() {
            controller.$onInit();
            $rootScope.$digest();
        });

        it('should have called the seen service', function () {
            expect(seenService.getSeen).to.have.been.calledOnce;
        });

        it('should have entries', function () {
            expect(controller.entries).to.not.be.empty;
        });
    });
});