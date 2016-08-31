/* global bard, sinon, mockExecuteData */
describe('Plugin: Execute-input.component', function () {
    var controller;
    var tasks = mockExecuteData.getMockTasks();

    beforeEach(function () {
        bard.appModule('plugins.execute');

        /* global $componentController, executeService, $q, $rootScope */
        bard.inject('$componentController', 'executeService', '$q', '$rootScope');

        sinon.stub(executeService, 'getTasks').returns($q.when(tasks));
    });

    beforeEach(function () {
        controller = $componentController('executeInput', null, {
            execute: sinon.stub()
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

        it('should have called the execute service', function () {
            expect(executeService.getTasks).to.have.been.calledOnce;
        });

        it('should have tasks', function () {
            expect(controller.tasks).to.not.be.empty;
        });

        it('should get have set the tasks correctly', function () {
            expect(controller.tasks).to.be.a('array');
            expect(controller.tasks).to.have.lengthOf(2);
        });
    });

    describe('startExecute()', function () {
        it('should exist', function () {
            expect(controller.startExecute).to.exist;
            expect(controller.startExecute).to.be.a('function');
        });

        it('should call the execute function', function () {
            controller.startExecute();

            expect(controller.execute).to.have.been.calledOnce;
        });

        it('should call the execute function with proper options', function () {
            controller.options = [
                {
                    name: 'learn',
                    value: false
                },
                {
                    name: 'no_cache',
                    value: true
                }
            ];

            var opts = {
                learn: false,
                'no_cache': true
            };

            controller.startExecute();

            expect(controller.execute).to.have.been.calledWith(opts);
        });
    });

    describe('searchTask()', function () {
        it('should exist', function () {
            expect(controller.searchTask).to.exist;
            expect(controller.searchTask).to.be.a('function');
        });

        it('should return an empty array when no searchterm is specified', function () {
            controller.searchTerm = '';

            var result = controller.searchTask();

            expect(result).to.be.a('array');
            expect(result).to.be.empty;
        });

        it('should return an array of tasks based on searchterm', function () {
            controller.tasks = ['TestingTask', 'OtherTask'];
            controller.searchTerm = 'Testing';

            var result = controller.searchTask();

            expect(result).to.exist;
            expect(result).to.have.lengthOf(1);
        });

        it('should ignore lower/uppercase', function () {
            controller.tasks = ['TestingTask', 'OtherTask'];
            controller.searchTerm = 'oThEr';

            var result = controller.searchTask();

            expect(result).to.exist;
            expect(result).to.have.lengthOf(1);
        });
    });
});