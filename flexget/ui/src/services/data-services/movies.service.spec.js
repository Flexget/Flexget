describe("Service: Movies", function () {
	var movieLists = mockMovieListData.getMovieLists();

	beforeEach(function () {
		bard.appModule('flexget.services', 'angular-cache');

		bard.inject('$rootScope', '$http', '$httpBackend', '$q', 'moviesService');
	});

	beforeEach(function () {
	});

	it("should exist", function () {
		expect(moviesService).to.exist;
		console.log(moviesService);
	});
});