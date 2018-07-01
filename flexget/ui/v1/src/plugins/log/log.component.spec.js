/* global bard, sinon */
describe('Plugin: Log.component', function () {
    var controller;

    beforeEach(function () {
        bard.appModule('plugins.log');

        /* global $componentController */
        bard.inject('$componentController');
    });

    beforeEach(function () {
        controller = $componentController('logView');
    });

    it('should exist', function () {
        expect(controller).to.exist;
    });

    describe('activation', function () {
        beforeEach(function () {
            sinon.stub(controller, 'start');
            controller.$onInit();
        });

        it('should call the start function', function () {
            expect(controller.start).to.have.been.calledOnce;
        });
    });

    describe('clear()', function () {
        it('should clear the gridOptions data', function () {
            controller.gridOptions.data = [
                { row: 'Test' }
            ];

            controller.clear();
            expect(controller.gridOptions.data).to.be.empty;
        });
    });

    describe('on destruction', function () {
        it('should call the stop function', function () {
            sinon.stub(controller, 'stop');

            controller.$onDestroy();

            expect(controller.stop).to.have.been.calleOnce;
        });
    });

    describe('toggle()', function () {
        it('should set call the stop function', function () {
            sinon.stub(controller, 'stop');

            controller.toggle();

            expect(controller.stop).to.have.been.calledOnce;
        });

        it('should set call the start function', function () {
            sinon.stub(controller, 'start');

            controller.status = 'Disconnected';

            controller.toggle();

            expect(controller.start).to.have.been.calledOnce;
        });
    });

    //TODO: TEST
    describe('stop()', function () {
        it('should get tested', function () {
            expect(true).to.be.true;
            /*controller.stream = true;

            sinon.stub(logService.startLogStream, 'abort');*/
        });
    });

    //TODO: TEST
    describe('start()', function () {
        it('should get tested', function () {
            expect(true).to.be.true;
        });
    });

    describe('refresh()', function () {
        it('should call the stop and start functions', function () {
            sinon.stub(controller, 'stop');
            sinon.stub(controller, 'start');

            controller.refresh();

            expect(controller.stop).to.have.been.calledOnce;
            expect(controller.start).to.have.been.calledOnce;
        });
    });
});