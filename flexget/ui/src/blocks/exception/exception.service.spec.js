describe("Blocks: Exception", function () {
	var mockErrorResponse = {
		status: 500,
		data: {
			message: "Failure"
		}
	}
	
	beforeEach(function () {
		bard.appModule('blocks.exception');

		bard.inject('exception', 'errorService', '$rootScope');
	});

	it("should exist", function () {
		expect(exception).to.exist;
	});
	
	describe('catcher()', function () {
		it('should exist', function () {
			expect(exception.catcher).to.exist;
		});

		it('should tell the errorService to open a toast', function () {
			sinon.stub(errorService, 'showToast');

			exception.catcher(mockErrorResponse).catch(function (err) {
				expect(err).to.equal(mockErrorResponse);
			});

			$rootScope.$apply();

			expect(errorService.showToast).to.have.been.calledOnce;
		});
	});
});