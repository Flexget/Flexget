require.config({
    baseUrl: "/ui/static/js/",
    paths: {
        'angular': '//cdnjs.cloudflare.com/ajax/libs/angular.js/1.4.1/angular.min',
        'ui-router': '//cdnjs.cloudflare.com/ajax/libs/angular-ui-router/0.2.15/angular-ui-router.min',
        'angularAMD': '//cdn.jsdelivr.net/angular.amd/0.2.0/angularAMD.min',
        'jquery': '//cdnjs.cloudflare.com/ajax/libs/jquery/2.1.4/jquery.min',
        'bootstrap': '//cdnjs.cloudflare.com/ajax/libs/twitter-bootstrap/3.3.5/js/bootstrap.min',
        'adminLTE': 'libs/adminLTE',
        'tv4': 'libs/tv4',
        'ObjectPath': 'libs/ObjectPath',
        'adminLTE': 'libs/adminLTE.min',
        'schema-form': 'libs/schema-form'
    },
    shim: {
        'angular': ['adminLTE'],
        'adminLTE': ['jquery', 'bootstrap'],
        'angularAMD': ['angular'],
        'ui-router': ['angular']
    },
    deps: ['app']
});