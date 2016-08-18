/* global angular */
(function () {
    'use strict';

    angular
        .module('blocks.router')
        .provider('routerHelper', routerHelperProvider);

    function routerHelperProvider($stateProvider, $urlRouterProvider, $windowProvider) {
        var $window = $windowProvider.$get();
        if (!($window.history && $window.history.pushState)) {
            $window.location.hash = '/';
        }

        //TODO: Figure out if htlm5Mode is possible
        //$locationProvider.html5Mode(true);

        this.configureStates = configureStates;
        this.$get = RouterHelper;

        var hasOtherwise = false;

        function configureStates(states, otherwisePath) {
            angular.forEach(states, function (state) {
                if (!state.config.root && !state.config.abstract) {
                    state.state = 'flexget.' + state.state;
                    state.config.template = '<' + state.config.component + ' flex layout="row"></' + state.config.component + '>';
                    delete state.config.component;
                }
                $stateProvider.state(state.state, state.config);

                if (state.when) {
                    for (var i = 0; i < state.when.length; i++) {
                        $urlRouterProvider.when(state.when[i], state.config.url);
                    }
                }
            });

            if (otherwisePath && !hasOtherwise) {
                hasOtherwise = true;
                $urlRouterProvider.otherwise(otherwisePath);
            }
        }

        function RouterHelper($location, $log, $rootScope, $state) {
            //var handlingStateChangeError = false;
            
            return {
                //configureStates: function () { },
                getStates: getStates
            };


            //init()

            /*function handleRoutingErrors() {
                //TODO: Convert to UI-router v1 (using transition.start etc.)
                $rootScope.$on('$stateChangeError', function (event, toState, toParams, fromState, fromParams, error) {
                    if (handlingStateChangeError) {
                        return;
                    }

                    var destination = (toState &&
                        (toState.title || toState.name || toState.loadedTemplateUrl)) ||
                        'unknown target';

                    var msg = 'Error routing to ' + destination + '. ' +
                        (error.data || '') + '. <br/>' + (error.statusText || '') +
                        ': ' + (error.status || '');

                    $log.log(msg);


                    handlingStateChangeError = true;
                    $location.path('/');

                    //TODO: Maybe add some logging here to indicate the routing failed
                });
            }*/

            //TODO: Check if needed to be re-enabled
            /*function init() {
                handleRoutingErrors();
            }*/

            function getStates() {
                return $state.get();
            }
        }
    }
}());