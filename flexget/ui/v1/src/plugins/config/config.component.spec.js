/* global bard, sinon, mockConfigData */
describe('Plugin: Config.component', function () {
    var controller;
    var rawConfig = mockConfigData.getMockRawConfig();

    beforeEach(function () {
        bard.appModule('plugins.config');

        /* global $componentController, $q, $rootScope, configService, CacheFactory */
        bard.inject('$componentController', '$q', '$rootScope', 'configService', 'CacheFactory');

        sinon.stub(configService, 'getRawConfig').returns($q.when(rawConfig));

        CacheFactory.clearAll();
    });

    beforeEach(function () {
        controller = $componentController('configView');
    });

    it('should exist', function () {
        expect(controller).to.exist;
    });

    describe('activation', function () {
        beforeEach(function () {
            controller.$onInit();
            $rootScope.$digest();
        });

        it('should have called the config service', function () {
            expect(configService.getRawConfig).to.have.been.calledOnce;
        });

        it('should setup the cache', function () {
            expect(CacheFactory.get('aceThemeCache')).to.exist;
        });

        it('should set the aceOptions and themes', function () {
            expect(controller.aceOptions).to.exist;

            expect(controller.themes).to.exist;
            expect(controller.themes).not.to.be.empty;
        });
    });
});