/* global bard, sinon, mockMovieListData */
describe('Plugin: Movie-list.Component', function () {
    var component, deferred;
    var movieList = mockMovieListData.getMovieListById();
    var movies = mockMovieListData.getMovieListMovies();
    var movie = mockMovieListData.getMovieListMovieById();

    beforeEach(function () {
        bard.appModule('plugins.movies');

        /* global $componentController, $mdDialog, $q, moviesService, $rootScope */
        bard.inject('$componentController', '$mdDialog', '$q', 'moviesService', '$rootScope');

        sinon.stub(moviesService, 'getListMovies').returns($q.when(movies));
    });

    beforeEach(function () {
        component = $componentController('movieList', null,
            {
                list: movieList,
                deleteMovieList: sinon.stub()
            });
    });

    it('should exist', function () {
        expect(component).to.exist;
    });

    describe('activation', function () {
        it('should have called the movies service when tabIndex is 0', function () {
            component.tabIndex = 0;

            component.$onInit();

            expect(moviesService.getListMovies).to.have.been.calledOnce;
        });

        it('should not call the movies service when tabIndex is not 0', function () {
            component.tabIndex = 3;

            component.$onInit();

            expect(moviesService.getListMovies).not.to.have.been.called;
        });
    });

    describe('loadMovies()', function () {
        it('should exist', function () {
            expect(component.loadMovies).to.exist;
            expect(component.loadMovies).to.be.a('function');
        });

        it('should set variables', function () {
            component.loadMovies();

            $rootScope.$digest();

            expect(component.movies).not.to.be.empty;
            expect(component.currentPage).to.exist;
            expect(component.totalMovies).to.exist;
            expect(component.pageSize).to.exist;
        });
    });

    describe('deleteMovie()', function () {
        beforeEach(function () {
            deferred = $q.defer();

            sinon.stub(moviesService, 'deleteMovie').returns(deferred.promise);
        });
        it('should exist', function () {
            expect(component.deleteMovie).to.exist;
            expect(component.deleteMovie).to.be.a('function');
        });

        it('should call the dialog show function', function () {
            sinon.spy($mdDialog, 'show');

            component.deleteMovie(movieList, movie);

            expect($mdDialog.show).to.have.been.calledOnce;
        });

        describe('confirmation', function () {
            it('should call the movies service', function () {
                sinon.stub($mdDialog, 'show').returns($q.resolve());

                component.deleteMovie(movieList, movie);

                $rootScope.$digest();

                expect(moviesService.deleteMovie).to.have.been.calledOnce;
            });

            it('should remove the movie from the list', function () {
                sinon.stub($mdDialog, 'show').returns($q.resolve());

                deferred.resolve();

                /* global angular */                
                component.movies = angular.copy(movies.movies);

                component.deleteMovie(movieList, movie);

                $rootScope.$digest();

                expect(component.movies.length).to.equal(movies.movies.length - 1);
            });
        });
    });
});