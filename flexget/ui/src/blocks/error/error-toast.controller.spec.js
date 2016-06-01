describe("Blocks: Error", function () {
	describe("Error-toast.controller", function () {
		var controller;

		var mockError = {
			"code": 500,
			"message": "Server error",
			"validation_errors": [
				{
					"message": "Something went wrong here",
					"path": "Something went wrong here as well",
					"schema_path": "Something went wrong here as well, it's also a long text",
					"validator": "string",
					"validator_value": "string"
				}
			]
		};

		beforeEach(function () {
			bard.appModule('blocks.error', function ($provide) {
				$provide.value('error', mockError);
			});
			bard.inject('$controller', '$mdDialog');
		});

		beforeEach(function () {
			controller = $controller('errorToastController');
		});

		it("should exist", function () {
			expect(controller).to.exist;
		});

		it("should have an error object", function () {
			expect(controller.error).to.exist;
		});
		
		describe('openDetails()', function () {
			it('should exist', function () {
				expect(controller.openDetails).to.exist;
				expect(controller.openDetails).to.be.a('function');
			});

			it('should open a dialog', function () {
				sinon.spy($mdDialog, 'show');

				controller.openDetails();

				expect($mdDialog.show).to.have.been.calledOnce;
			});
		});
	});
});