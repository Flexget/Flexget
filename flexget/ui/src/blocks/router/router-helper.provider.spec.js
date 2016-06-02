describe("Blocks: Router", function () {
	beforeEach(function () {
		bard.appModule('blocks.router');
		bard.inject('routerHelper');
	});

	it("should exist", function () {
		expect(routerHelper).to.exist;
	});

	//TODO: Expand these tests, create mock routes and route to them to test?
});