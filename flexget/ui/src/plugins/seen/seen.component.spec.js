describe("Plugin: Seen.component", function () {
	var controller;
	var seen = mockSeenData.getMockSeen();

	beforeEach(function () {
		bard.appModule('plugins.seen');

		bard.inject('$componentController', 'seenService', '$q', '$rootScope');
		
		sinon.stub(seenService, 'getSeen').returns($q.when(seen));
	});

	beforeEach(function () {
		controller = $componentController('seenView');
	});

	it("should exist", function () {
		expect(controller).to.exist;
	});

	describe("activation", function () {
		beforeEach(function() {
			controller.$onInit();
			$rootScope.$apply();
		});
		
		it("should have entries", function () {
			expect(controller.entries).to.not.be.empty;
		});
	});
});