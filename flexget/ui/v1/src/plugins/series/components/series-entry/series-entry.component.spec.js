/* global bard, sinon, mockSeriesData */
describe('Plugin: Series-Entry.Component', function () {
    var component;
    var metadata = mockSeriesData.getShowMetadata();
    var show = mockSeriesData.getShow();

    beforeEach(function () {
        bard.appModule('plugins.series');

        /* global $componentController, $q, seriesService, $rootScope */
        bard.inject('$componentController', '$q', 'seriesService', '$rootScope');

        sinon.stub(seriesService, 'getShowMetadata').returns($q.when(metadata));
    });

    beforeEach(function () {
        component = $componentController('seriesEntry');
    });

    it('should exist', function () {
        expect(component).to.exist;
    });

    describe('activation', function () {
        beforeEach(function () {
            /* global angular */
            component.show = angular.copy(show);
            component.$onInit();
            $rootScope.$digest();
        });

        it('should call the series service', function () {
            expect(seriesService.getShowMetadata).to.have.been.calledOnce;
        });

        it('should set the show\'s metadata', function () {
            expect(component.show.metadata).to.exist;
            expect(component.show.metadata).not.to.be.empty;
        });
    });
});