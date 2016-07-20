describe('Plugin: Seen-entry.component', function () {
	var controller;

	beforeEach(function () {
		bard.appModule('plugins.seen');

		bard.inject('$componentController', '$rootScope');
	});

	beforeEach(function () {
		controller = $componentController('seenEntry');
	});

	it('should exist', function () {
		expect(controller).to.exist;
	});
});