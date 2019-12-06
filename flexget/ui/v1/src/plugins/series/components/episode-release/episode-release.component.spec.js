/* global bard, mockSeriesData */
describe('Plugin: Episode-Release.Component', function () {
    var component, deferred;
    var release = mockSeriesData.getRelease();
    var episode = mockSeriesData.getEpisode();
    var show = mockSeriesData.getShow();

    beforeEach(function () {
        bard.appModule('plugins.series');

        /* global $componentController, $q, seriesService, $rootScope, $mdDialog */
        bard.inject('$componentController', '$q', 'seriesService', '$rootScope', '$mdDialog');
    });

    beforeEach(function () {
        component = $componentController('episodeRelease', null, {
            show: show,
            episode: episode.episode,
            release: release
        });
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
            sinon.stub($mdDialog, 'cancel');

            component.cancel();

            expect($mdDialog.cancel).to.have.been.calledOnce;
        });
    });

    describe('resetRelease()', function () {
        beforeEach(function () {
            deferred = $q.defer();
            sinon.stub(seriesService, 'resetRelease').returns(deferred.promise);

        });

        it('should exist', function () {
            expect(component.resetRelease).to.exist;
            expect(component.resetRelease).to.be.a('function');
        });

        it('should open a dialog', function () {
            sinon.spy($mdDialog, 'show');

            component.resetRelease();

            expect($mdDialog.show).to.have.been.calledOnce;
        });

        describe('confirmation', function () {
            it('should call the series service', function () {
                sinon.stub($mdDialog, 'show').returns($q.resolve());

                component.resetRelease(episode);

                $rootScope.$digest();

                expect(seriesService.resetRelease).to.have.been.calledOnce;
            });
        });
    });

    describe('forgetRelease()', function () {
        beforeEach(function () {
            deferred = $q.defer();
            sinon.stub(seriesService, 'forgetRelease').returns(deferred.promise);

        });

        it('should exist', function () {
            expect(component.forgetRelease).to.exist;
            expect(component.forgetRelease).to.be.a('function');
        });

        it('should call the dialog show function', function () {
            sinon.spy($mdDialog, 'show');

            component.forgetRelease();

            expect($mdDialog.show).to.have.been.calledOnce;
        });

        describe('confirmation', function () {
            it('should call the series service', function () {
                sinon.stub($mdDialog, 'show').returns($q.resolve());

                component.forgetRelease();

                $rootScope.$digest();

                expect(seriesService.forgetRelease).to.have.been.calledOnce;
            });
        });
    });
});