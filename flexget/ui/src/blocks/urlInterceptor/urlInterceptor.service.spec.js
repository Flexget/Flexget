describe("Blocks: UrlInterceptor", function () {
	beforeEach(function () {
		bard.appModule('blocks.urlInterceptor');

		bard.inject('urlInterceptor');

		//sinon.spy(exception, 'catcher');
	});

	it("should exist", function () {
		expect(urlInterceptor).to.exist;
	});
});