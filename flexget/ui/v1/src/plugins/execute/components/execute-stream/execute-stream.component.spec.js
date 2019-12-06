/* global bard, sinon */
describe('Plugin: Execute-stream.component', function () {
    var controller;

    beforeEach(function () {
        bard.appModule('plugins.execute');

        /* global $componentController, executeService, $rootScope */
        bard.inject('$componentController', 'executeService', '$rootScope');

        sinon.spy(executeService, 'executeTasks');
    });

    beforeEach(function () {
        controller = $componentController('executeStream', null, {
            stopStream: sinon.stub(),
            options: {
                tasks: ['FillMovieQueue', 'DownloadMovies']
            }
        });
    });

    it('should exist', function () {
        expect(controller).to.exist;
    });

    describe('activation', function () {
        beforeEach(function () {
            controller.$onInit();
            $rootScope.$digest();
        });

        it('should set the tasks based on the options', function () {
            var tasks = [
                {
                    entries: [],
                    name: 'FillMovieQueue',
                    percent: 0,
                    status: 'pending'
                },
                {
                    entries: [],
                    name: 'DownloadMovies',
                    percent: 0,
                    status: 'pending'
                }
            ];

            expect(controller.streamTasks).to.eql(tasks);
        });

        it('should start the stream', function () {
            //TODO: Test the subparts of the stream (log, progress, ...)
            expect(executeService.executeTasks).to.have.been.calledOnce;
        });
    });

    describe('clear()', function () {
        it('should exist', function () {
            expect(controller.clear).to.exist;
            expect(controller.clear).to.be.a('function');
        });

        it('should stop the stream', function () {
            controller.clear();

            //TODO: Test the stream stopping
        });

        it('should call the stopStream function from the main component', function () {
            controller.clear();

            expect(controller.stopStream).to.have.been.calledOnce;
        });
    });
});