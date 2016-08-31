/* global bard, sinon, angular, mockSeriesData */
describe('Plugin: Series-Episodes.Component', function () {
    var component, deferred;
    var episodes = mockSeriesData.getEpisodes();
    var episode = mockSeriesData.getEpisode();
    var show = mockSeriesData.getShow();

    beforeEach(function () {
        bard.appModule('plugins.series');

        /* global $componentController, $q, seriesService, $rootScope, $mdDialog */
        bard.inject('$componentController', '$q', 'seriesService', '$rootScope', '$mdDialog');

        sinon.stub(seriesService, 'getEpisodes').returns($q.when(episodes));
    });

    beforeEach(function () {
        component = $componentController('seriesEpisodesView');
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
            expect(seriesService.getEpisodes).to.have.been.calledOnce;
        });

        it('should set the episodes list', function () {
            expect(component.episodes).to.exist;
            expect(component.episodes).not.to.be.empty;
        });
    });

    describe('deleteEpisode()', function () {
        beforeEach(function () {
            component.show = angular.copy(show);

            deferred = $q.defer();
            sinon.stub(seriesService, 'deleteEpisode').returns(deferred.promise);

        });
        it('should exist', function () {
            expect(component.deleteEpisode).to.exist;
            expect(component.deleteEpisode).to.be.a('function');
        });

        it('should call the dialog show function', function () {
            sinon.spy($mdDialog, 'show');

            component.deleteEpisode(episode);

            expect($mdDialog.show).to.have.been.calledOnce;
        });

        describe('confirmation', function () {
            it('should call the series service', function () {
                sinon.stub($mdDialog, 'show').returns($q.resolve());

                component.deleteEpisode(episode);

                $rootScope.$digest();

                expect(seriesService.deleteEpisode).to.have.been.calledOnce;
            });

            it('should remove the episode from all episodes', function () {
                sinon.stub($mdDialog, 'show').returns($q.resolve());

                deferred.resolve();

                component.episodes = angular.copy(episodes.episodes);

                component.deleteEpisode(episode);

                $rootScope.$digest();

                expect(component.episodes.length).to.equal(episodes.episodes.length - 1);
            });
        });
    });
});