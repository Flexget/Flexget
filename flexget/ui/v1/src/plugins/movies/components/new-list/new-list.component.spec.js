/* global bard, sinon, mockMovieListData */
describe('Plugin: New-list.Component', function () {
    var component, deferred;
    var createdList = mockMovieListData.createMovieList();

    beforeEach(function () {
        bard.appModule('plugins.movies');

        /* global $componentController, $mdDialog, $q, moviesService, $rootScope */
        bard.inject('$componentController', '$mdDialog', '$q', 'moviesService', '$rootScope');
    });

    beforeEach(function () {
        component = $componentController('newList');
    });

    it('should exist', function () {
        expect(component).to.exist;
    });

    describe('cancel()', function () {
        it('should exist', function () {
            expect(component.cancel).to.exist;
            expect(component.cancel).to.be.a('function');
        });

        it('should close the dialog', function () {
            sinon.spy($mdDialog, 'cancel');

            component.cancel();

            expect($mdDialog.cancel).to.have.been.calledOnce;
        });
    });

    describe('saveList()', function () {
        beforeEach(function () {
            deferred = $q.defer();

            sinon.stub(moviesService, 'createList').returns(deferred.promise);
        });

        it('should exist', function () {
            expect(component.saveList).to.exist;
            expect(component.saveList).to.be.a('function');
        });

        it('should call the movies service', function () {
            component.saveList();

            expect(moviesService.createList).to.have.been.calledOnce;
        });

        it('should close the dialog when successfull', function () {
            sinon.spy($mdDialog, 'hide');

            deferred.resolve();

            component.saveList();

            $rootScope.$digest();

            expect($mdDialog.hide).to.have.been.calledOnce;
        });

        it('should close the dialog with the new list', function () {
            sinon.spy($mdDialog, 'hide');

            deferred.resolve(createdList);

            component.saveList();

            $rootScope.$digest();

            expect($mdDialog.hide).to.have.been.calledWith(createdList);
        });
    });
});