/* global bard, sinon */
describe('Blocks: Exception', function () {
    var mockErrorResponse = {
        status: 500,
        data: {
            message: 'Failure'
        }
    };

    beforeEach(function () {
        bard.appModule('blocks.exception');

        /* global exception, errorService, $rootScope */
        bard.inject('exception', 'errorService', '$rootScope');
    });

    it('should exist', function () {
        expect(exception).to.exist;
    });

    describe('catcher()', function () {
        it('should exist', function () {
            expect(exception.catcher).to.exist;
        });

        it('should tell the errorService to open a toast', function () {
            sinon.stub(errorService, 'showToast');

            exception.catcher(mockErrorResponse).catch(function (err) {
                expect(err).to.equal(mockErrorResponse.data);
            });

            $rootScope.$digest();

            expect(errorService.showToast).to.have.been.calledOnce;
        });

        it('should not open a toast when request failure is auth related', function () {
            sinon.stub(errorService, 'showToast');

            mockErrorResponse.status = 401;

            exception.catcher(mockErrorResponse).catch(function (err) {
                expect(err).to.equal(mockErrorResponse.data);
            });

            $rootScope.$digest();

            expect(errorService.showToast).not.to.have.been.called;
        });
    });
});