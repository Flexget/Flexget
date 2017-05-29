/* global bard, sinon, mockSeriesData */
describe('Plugin: Series-Episode.Component', function () {
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
        component = $componentController('seriesEpisode', null, {
            show: show,
            episode: episode.episode
        });
    });

    it('should exist', function () {
        expect(component).to.exist;
    });

    describe('showReleases()', function () {
        it('should exist', function () {
            expect(component.showReleases).to.exist;
            expect(component.showReleases).to.be.a('function');
        });

        it('should open a dialog', function () {
            sinon.spy($mdDialog, 'show');

            component.showReleases();

            expect($mdDialog.show).to.have.been.calledOnce;
        });
    });

    describe('deleteReleases()', function () {
        beforeEach(function () {
            deferred = $q.defer();
            sinon.stub(seriesService, 'deleteReleases').returns(deferred.promise);

        });
        it('should exist', function () {
            expect(component.deleteReleases).to.exist;
            expect(component.deleteReleases).to.be.a('function');
        });

        it('should call the dialog show function', function () {
            sinon.spy($mdDialog, 'show');

            component.deleteReleases();

            expect($mdDialog.show).to.have.been.calledOnce;
        });

        describe('confirmation', function () {
            it('should call the series service', function () {
                sinon.stub($mdDialog, 'show').returns($q.resolve());

                component.deleteReleases();

                $rootScope.$digest();

                expect(seriesService.deleteReleases).to.have.been.calledOnce;
            });

            it('should remove the episode from all episodes', function () {
                sinon.stub($mdDialog, 'show').returns($q.resolve());

                deferred.resolve();

                component.deleteReleases();

                $rootScope.$digest();

                expect(component.releases).not.to.exist;
                expect(component.episode.episode_number_of_releases).to.equal(0);
            });
        });
    });

    describe('resetReleases()', function () {
        beforeEach(function () {
            deferred = $q.defer();
            sinon.stub(seriesService, 'resetReleases').returns(deferred.promise);
        });
        it('should exist', function () {
            expect(component.resetReleases).to.exist;
            expect(component.resetReleases).to.be.a('function');
        });

        it('should call the dialog show function', function () {
            sinon.spy($mdDialog, 'show');

            component.resetReleases(episode);

            expect($mdDialog.show).to.have.been.calledOnce;
        });

        describe('confirmation', function () {
            it('should call the series service', function () {
                sinon.stub($mdDialog, 'show').returns($q.resolve());

                component.resetReleases(episode);

                $rootScope.$digest();

                expect(seriesService.resetReleases).to.have.been.calledOnce;
            });
        });
    });
});