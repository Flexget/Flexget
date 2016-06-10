describe("Plugin: Series-Entry.Component", function () {
	var component, deferred;
	var metadata = mockSeriesData.getShowMetadata();
	var show = mockSeriesData.getShow();

	beforeEach(function () {
		bard.appModule('plugins.series');
		bard.inject('$componentController', '$q', 'seriesService', '$rootScope', '$mdDialog');

		sinon.stub(seriesService, 'getShowMetadata').returns($q.when(metadata));
	});

	beforeEach(function () {
		component = $componentController('seriesEntry');
	});

	it("should exist", function () {
		expect(component).to.exist;
	});

	describe('activation', function () {
		beforeEach(function () {
			component.show = angular.copy(show);
			component.$onInit();
			$rootScope.$apply();
		});

		it('should call the series service', function () {
			expect(seriesService.getShowMetadata).to.have.been.calledOnce;
		});

		it('should set the show\'s metdata', function () {
			expect(component.show.metadata).to.exist;
			expect(component.show.metadata).not.to.be.empty;
		});
	});
});