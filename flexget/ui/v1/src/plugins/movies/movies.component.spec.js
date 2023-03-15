/* global bard, sinon, angular, mockMovieListData */
describe('Plugin: Movies.Component', function () {
    var component, deferred;
    var lists = mockMovieListData.getMovieLists();
    var list = mockMovieListData.getMovieListById();

    beforeEach(function () {
        bard.appModule('plugins.movies');

        /* global $componentController, $q, moviesService, $rootScope, $mdDialog */
        bard.inject('$componentController', '$q', 'moviesService', '$rootScope', '$mdDialog');

        sinon.stub(moviesService, 'getLists').returns($q.when(lists));
    });

    beforeEach(function () {
        component = $componentController('moviesView');
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
            expect(moviesService.getLists).to.have.been.calledOnce;
        });

        it('should set the metadata values', function () {
            expect(component.lists).to.exist;
            expect(component.lists).not.to.be.empty;
        });
    });

    describe('deleteList()', function () {
        var event;
        beforeEach(function () {
            event = $rootScope.$emit('click');
            deferred = $q.defer();

            sinon.stub(moviesService, 'deleteList').returns(deferred.promise);
        });

        it('should exist', function () {
            expect(component.deleteList).to.exist;
            expect(component.deleteList).to.be.a('function');
        });

        it('should call the dialog show function', function () {
            sinon.spy($mdDialog, 'show');

            component.deleteList(event, list);

            expect($mdDialog.show).to.have.been.calledOnce;
        });

        describe('confirmation', function () {
            it('should call the movies service', function () {
                sinon.stub($mdDialog, 'show').returns($q.resolve());

                component.deleteList(event, list);

                $rootScope.$digest();

                expect(moviesService.deleteList).to.have.been.calledOnce;
            });

            it('should remove the list from all lists', function () {
                sinon.stub($mdDialog, 'show').returns($q.resolve());

                deferred.resolve();
                            
                component.lists = angular.copy(lists.movie_lists);

                component.deleteList(event, list);

                $rootScope.$digest();

                expect(component.lists.length).to.equal(lists.movie_lists.length - 1);
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

            $rootScope.$digest();

            expect(component.lists.length).to.equal(lists.movie_lists.length + 1);
        });
    });
});