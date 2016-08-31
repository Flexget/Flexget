/* global bard */
describe('Plugin: Execute.Filter', function () {
    beforeEach(function () {

        bard.appModule('plugins.execute');

        /* global $filter */
        bard.inject('$filter');
    });

    it('should exist', function () {
        expect($filter('executePhaseFilter')).to.exist;
        expect($filter('executePhaseFilter')).to.be.a('function');
    });

    it('should return the correct phase description', function () {
        var filter = $filter('executePhaseFilter');

        var output = filter('input');
        expect(output).to.equal('Gathering Entries');

        output = filter('metainfo');
        expect(output).to.equal('Figuring out meta data');

        output = filter('filter');
        expect(output).to.equal('Filtering Entries');

        output = filter('download');
        expect(output).to.equal('Downloading Accepted Entries');

        output = filter('modify');
        expect(output).to.equal('Modifying Entries');

        output = filter('output');
        expect(output).to.equal('Executing Outputs');

        output = filter('exit');
        expect(output).to.equal('Finished');
    });

    it('should return "processing" when an unknown phase is specified', function () {
        var output = $filter('executePhaseFilter')('NotExistingPhase');
        expect(output).to.equal('Processing');
    });
});