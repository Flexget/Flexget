describe("Service: Movies", function () {
	var movieLists = mockMovieListData.getMovieLists();

	beforeEach(function () {
		bard.appModule('flexget.services');

		bard.inject('$httpBackend', 'moviesService');
	});

	it("should exist", function () {
		expect(moviesService).to.exist;
	});
});