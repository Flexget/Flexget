/* global bard, sinon, mockMovieListData */
describe('Plugin: Movie-Entry.Component', function () {
    var component;
    var movie = mockMovieListData.getMovieListMovieById();
    var metadata = mockMovieListData.getMovieMetadata();

    beforeEach(function () {
        bard.appModule('plugins.movies');

        /* global $componentController, $q, moviesService, $rootScope */
        bard.inject('$componentController', '$q', 'moviesService', '$rootScope');

        sinon.stub(moviesService, 'getMovieMetadata').returns($q.when(metadata));
    });

    beforeEach(function () {
        component = $componentController('movieEntry', null,
            {
                movie: movie,
            });
    });

    it('should exist', function () {
        expect(component).to.exist;
    });

    describe('activation', function () {
        beforeEach(function () {
            component.$onInit();
            $rootScope.$digest();
        });

        it('should call the movies service', function () {
            expect(moviesService.getMovieMetadata).to.have.been.calledOnce;
        });

        it('should set the metadata values', function () {
            expect(component.metadata).to.exist;
        });
    });
});