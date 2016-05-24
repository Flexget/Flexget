describe("Plugin: History.component", function() {
   var controller;
   var routeObj;
   
   beforeEach(function() {
        bard.appModule('flexget.plugins.history', function($provide) {
            $provide.provider('route', function() {
                this.$get = function() {
                    //var register  = sinon.spy('register');

                    function register() {};                   

                    return {
                        register: register
                    }
                }
            });
            
            $provide.service('sideNav', function() {
                this.register = function() {};
            });
        });
        
        bard.inject('$componentController', '$rootScope', '$http', '$httpBackend', 'route', 'sideNav');
   });
   
   beforeEach(function() {
       $httpBackend.expectGET('/api/history/').respond(200, { entries: "test" });
       
       controller = $componentController('historyView');
   });   
   
   it("should exist", function() {
       expect(controller).to.exist;
   });
   
   describe("activation", function() {
       it("should get entries", function() {
            $httpBackend.flush();
            
            expect(controller.entries).to.exist;
       });
   })
});