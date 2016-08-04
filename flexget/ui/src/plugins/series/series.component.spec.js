/* global bard, sinon, mockSeriesData */
describe('Plugin: Series.Component', function () {
    var component, deferred;
    var shows = mockSeriesData.getShows();
    var show = mockSeriesData.getShow();

    beforeEach(function () {
        bard.appModule('plugins.series');

        /* global $componentController, $q, seriesService, $rootScope, $mdDialog, $timeout */
        bard.inject('$componentController', '$q', 'seriesService', '$rootScope', '$mdDialog', '$timeout');

        sinon.stub(seriesService, 'getShows').returns($q.when(shows));
    });

    beforeEach(function () {
        component = $componentController('seriesView');
    });

    it('should exist', function () {
        expect(component).to.exist;
    });

    describe('activation', function () {
        beforeEach(function () {
            component.$onInit();
            $rootScope.$digest();
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

                $rootScope.$digest();

                expect(seriesService.deleteShow).to.have.been.calledOnce;
            });

            it('should remove the list from all lists', function () {
                sinon.stub($mdDialog, 'show').returns($q.resolve());

                deferred.resolve();

                component.forgetShow(show);

                $rootScope.$digest();

                expect(seriesService.getShows).to.have.been.calledOnce;
            });
        });
    });

    describe('toggleEpisodes()', function () {
        it('should exist', function () {
            expect(component.toggleEpisodes).to.exist;
            expect(component.toggleEpisodes).to.be.a('function');
        });

        it('should set the selectedShow to the clicked show', function () {
            component.toggleEpisodes(show);

            $timeout.flush();

            expect(component.selectedShow).to.exist;
            expect(component.selectedShow).to.equal(show);
        });

        it('should unset the selectedShow when the same show is selected again', function () {
            component.selectedShow = show;

            component.toggleEpisodes(show);

            expect(component.selectedShow).not.to.exist;
        });

        it('should set the selectedShow to a different show', function () {
            component.selectedShow = {
                name: 'Testing'
            };

            component.toggleEpisodes(show);

            $timeout.flush();

            expect(component.selectedShow).to.exist;
            expect(component.selectedShow).to.equal(show);
        });
    });

    describe('search()', function () {
        beforeEach(function () {
            sinon.stub(seriesService, 'searchShows').returns($q.when(shows));
        });

        it('should exist', function () {
            expect(component.search).to.exist;
            expect(component.search).to.be.a('function');
        });

        it('should call the series service', function () {
            component.searchTerm = 'iZom';

            component.search();

            expect(seriesService.searchShows).to.have.been.calledOnce;
        });

        it('should set the series list', function () {
            component.searchTerm = 'iZom';

            component.search();

            $rootScope.$digest();

            expect(component.series).to.exist;
            expect(component.series).to.have.length.above(0);
        });

        it('should call the complete list when searchterm is empty', function () {
            component.search();

            expect(seriesService.getShows).to.have.been.calledOnce;
        });

        it('should call the complete list after a search term has been removed', function () {
            component.searchTerm = 'iZom';

            component.search();

            component.searchTerm = '';

            component.search();

            expect(seriesService.getShows).to.have.been.calledOnce;
        });
    });
});