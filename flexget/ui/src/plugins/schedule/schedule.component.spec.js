/* global bard, sinon, mockSchedulesData */
describe('Plugin: Schedule.component', function () {
    var controller;
    var schedules = mockSchedulesData.getMockSchedules();

    beforeEach(function () {
        bard.appModule('plugins.schedule');

        /* global $componentController, schedulesService, $q, $rootScope */
        bard.inject('$componentController', 'schedulesService', '$q', '$rootScope');

        sinon.stub(schedulesService, 'getSchedules').returns($q.when(schedules));
    });

    beforeEach(function () {
        controller = $componentController('scheduleView');
    });

    it('should exist', function () {
        expect(controller).to.exist;
    });

    describe('activation', function () {
        beforeEach(function() {
            controller.$onInit();
            $rootScope.$digest();
        });

        it('should have called the schedules service', function () {
            expect(schedulesService.getSchedules).to.have.been.calledOnce;
        });

        it('should have entries', function () {
            expect(controller.models).to.not.be.empty;
        });
    });
});