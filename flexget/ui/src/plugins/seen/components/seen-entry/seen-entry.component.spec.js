/* global bard */
describe('Plugin: Seen-entry.component', function () {
    var controller;

    beforeEach(function () {
        bard.appModule('plugins.seen');

        /* global $componentController */
        bard.inject('$componentController');
    });

    beforeEach(function () {
        controller = $componentController('seenEntry');
    });

    it('should exist', function () {
        expect(controller).to.exist;
    });
});