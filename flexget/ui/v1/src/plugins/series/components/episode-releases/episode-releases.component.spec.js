/* global bard, sinon, mockSeriesData */
describe('Plugin: Episode-Releases.Component', function () {
    var component, deferred;
    var releases = mockSeriesData.getReleases();
    var episode = mockSeriesData.getEpisode();
    var show = mockSeriesData.getShow();

    beforeEach(function () {
        bard.appModule('plugins.series');

        /* global $componentController, $q, seriesService, $rootScope, $mdDialog */
        bard.inject('$componentController', '$q', 'seriesService', '$rootScope', '$mdDialog');

        sinon.stub(seriesService, 'loadReleases').returns($q.when(releases));
    });

    beforeEach(function () {
        component = $componentController('episodeReleases', null, {
            show: show,
            episode: episode.episode
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

        it('should call the series service', function () {
            expect(seriesService.loadReleases).to.have.been.calledOnce;
        });

        it('should set the episodes list', function () {
            expect(component.releases).to.exist;
            expect(component.releases).not.to.be.empty;
        });
    });

    describe('cancel()', function () {
        it('should exist', function () {
            expect(component.cancel).to.exist;
            expect(component.cancel).to.be.a('function');
        });

        it('should close the dialog', function () {
            sinon.stub($mdDialog, 'cancel');

            component.cancel();

            expect($mdDialog.cancel).to.have.been.calledOnce;
        });
    });
});