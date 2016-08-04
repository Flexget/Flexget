/* global bard, sinon */
describe('Blocks: Error', function () {
    describe('Error-dialog.component', function () {
        var controller;

        var mockError = {
            'code': 500,
            'message': 'Server error',
            'validation_errors': [
                {
                    'message': 'Something went wrong here',
                    'path': 'Something went wrong here as well',
                    'schema_path': 'Something went wrong here as well, it\'s also a long text',
                    'validator': 'string',
                    'validator_value': 'string'
                }
            ]
        };

        beforeEach(function () {
            bard.appModule('blocks.error');

            /* global $componentController, $mdDialog */
            bard.inject('$componentController', '$mdDialog');
        });

        beforeEach(function () {
            controller = $componentController('errorDialog', null,
                {
                    error: mockError
                });
        });

        it('should exist', function () {
            expect(controller).to.exist;
        });

        it('should have an error object', function () {
            expect(controller.error).to.exist;
        });

        describe('close()', function () {
            it('should exist', function () {
                expect(controller.close).to.exist;
                expect(controller.close).to.be.a('function');
            });

            it('should close the dialog', function () {
                sinon.spy($mdDialog, 'hide');

                controller.close();

                expect($mdDialog.hide).to.have.been.calledOnce;
            });
        });
    });
});