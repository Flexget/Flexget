/* global bard, sinon, mockExecuteData */
describe('Plugin: Execute.component', function () {
    var controller;
    var queue = mockExecuteData.getMockQueue();

    beforeEach(function () {
        bard.appModule('plugins.execute');

        /* global $componentController, executeService, $q, $rootScope, $interval */
        bard.inject('$componentController', 'executeService', '$q', '$rootScope','$interval');

        sinon.stub(executeService, 'getQueue').returns($q.when(queue));
    });

    beforeEach(function () {
        controller = $componentController('executeView');
    });

    it('should exist', function () {
        expect(controller).to.exist;
    });

    describe('activation', function () {
        beforeEach(function() {
            controller.$onInit();
            $rootScope.$digest();
        });

        it('should have called the execute service', function () {
            expect(executeService.getQueue).to.have.been.calledOnce;
        });

        it('should have entries', function () {
            expect(controller.running).to.not.be.empty;
        });

        it('should get the new queue after 3 seconds', function () {
            $interval.flush(3000);

            expect(executeService.getQueue).to.have.been.calledTwice;
        });
    });

    describe('stopStream()', function () {
        it('should exist', function () {
            expect(controller.stopStream).to.exist;
            expect(controller.stopStream).to.be.a('function');
        });

        it('should clear the options', function () {
            controller.options = {
                Test: 'Testing'
            };

            controller.stopStream();

            expect(controller.options).to.be.undefined;
        });

        it('should set the stream variable to false', function () {
            controller.streaming = true;

            controller.stopStream();

            expect(controller.streaming).to.be.false;
        });
    });

    describe('execute()', function () {
        it('should exist', function () {
            expect(controller.execute).to.exist;
            expect(controller.execute).to.be.a('function');
        });

        it('should set the stream variable to true', function () {
            controller.streaming = false;

            controller.execute({});

            expect(controller.streaming).to.be.true;
        });

        it('should set the options variable', function () {
            var options = {
                test: true
            };

            var tasks = ['TestingTask', 'OtherTask'];

            controller.execute(options, tasks);

            expect(controller.options).to.exist;
            expect(controller.options.tasks).to.equal(tasks);
        });
    });

    describe('destroy', function () {
        beforeEach(function () {
            sinon.stub($interval, 'cancel');

            controller.$onDestroy();
        });

        it('should stop the interval timer', function () {
            expect($interval.cancel).to.have.been.calledOnce;
        });
    });
});