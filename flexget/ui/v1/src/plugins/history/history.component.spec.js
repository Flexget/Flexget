/* global bard, sinon, mockHistoryData */
describe('Plugin: History.component', function () {
    var controller;
    var history = mockHistoryData.getMockHistory();

    beforeEach(function () {
        bard.appModule('plugins.history');

        /* global $componentController, historyService, $q, $rootScope */
        bard.inject('$componentController', 'historyService', '$q', '$rootScope');

        sinon.stub(historyService, 'getHistory').returns($q.when(history));
    });

    beforeEach(function () {
        controller = $componentController('historyView');
    });

    it('should exist', function () {
        expect(controller).to.exist;
    });

    describe('activation', function () {
        beforeEach(function() {
            controller.$onInit();
            $rootScope.$digest();
        });

        it('should have called the history service', function () {
            expect(historyService.getHistory).to.have.been.calledOnce;
        });

        it('should have entries', function () {
            expect(controller.entries).to.not.be.empty;
        });
    });
});