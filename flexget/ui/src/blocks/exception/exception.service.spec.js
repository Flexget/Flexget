describe("Blocks: Exception", function () {
	beforeEach(function () {
		bard.appModule('blocks.exception');

		bard.inject('exception');

		//sinon.spy(exception, 'catcher');
	});

	it("should exist", function () {
		expect(exception).to.exist;
	});
});