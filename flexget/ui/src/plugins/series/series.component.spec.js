describe("Plugin: Series.Component", function () {
	var component, deferred;
	var shows = mockSeriesData.getShows();
	var show = mockSeriesData.getShow();

	beforeEach(function () {
		bard.appModule('plugins.series');
		bard.inject('$componentController', '$q', 'seriesService', '$rootScope', '$mdDialog');

		sinon.stub(seriesService, 'getShows').returns($q.when(shows));
	});

	beforeEach(function () {
		component = $componentController('seriesView');
	});

	it("should exist", function () {
		expect(component).to.exist;
	});

	describe('activation', function () {
		beforeEach(function () {
			component.$onInit();
			$rootScope.$apply();
		});

		it('should call the series service', function () {
			expect(seriesService.getShows).to.have.been.calledOnce;
		});

		it('should set the series list', function () {
			expect(component.series).to.exist;
			expect(component.series).not.to.be.empty;
		});
	});

	describe('forgetShow()', function () {
		beforeEach(function () {
			deferred = $q.defer();

			sinon.stub(seriesService, 'deleteShow').returns(deferred.promise);
		});

		it('should exist', function () {
			expect(component.forgetShow).to.exist;
			expect(component.forgetShow).to.be.a('function');
		});

		it('should call the dialog show function', function () {
			sinon.spy($mdDialog, 'show');

			component.forgetShow(show);

			expect($mdDialog.show).to.have.been.calledOnce;
		});

		describe('confirmation', function () {
			it('should call the series service', function () {
				sinon.stub($mdDialog, 'show').returns($q.resolve());
				
				component.forgetShow(show);

				$rootScope.$apply();

				expect(seriesService.deleteShow).to.have.been.calledOnce;
			});

			it('should remove the list from all lists', function () {
				sinon.stub($mdDialog, 'show').returns($q.resolve());

				deferred.resolve();

				component.forgetShow(show);

				$rootScope.$apply();

				expect(seriesService.getShows).to.have.been.calledOnce;
			});
		});
	});

	describe('newList()', function () {
		it('should exist', function () {
			expect(component.newList).to.exist;
			expect(component.newList).to.be.a('function');
		});

		it('should call the dialog show function', function () {
			var event = $rootScope.$emit('click');

			sinon.spy($mdDialog, 'show');

			component.newList(event);

			expect($mdDialog.show).to.have.been.calledOnce;
		});

		it('should add the new list to all lists', function () {
			var event = $rootScope.$emit('click');

			sinon.stub($mdDialog, 'show').returns($q.when(list));

			component.lists = angular.copy(lists.movie_lists);

			component.newList(event);

			$rootScope.$apply();

			expect(component.lists.length).to.equal(lists.movie_lists.length + 1);
		})
	});
});