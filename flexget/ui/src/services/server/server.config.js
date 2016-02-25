(function () {
    'use strict';

    angular.module('flexget.services')
        .run(serverConfig);

    function serverConfig(toolBar, server, Dialog) {

        var reload = function () {
            server.reload()
                .success(function() {
                    var options = {
                        title: "Reload success",
                        body: "Your config file has been successfully reloaded.",
                        ok: "Ok"
                    }
                    Dialog.open(options);
                })
                .error(function(error) {
                    console.log("error occured: " + error)
                    var options = {
                        title: "Reload failed",
                        body: "Oops, something went wrong: " + error.message,
                        ok: "Ok"
                    }
                    Dialog.open(options);
                });
        };

        var doShutdown = function () {
            window.stop(); // Kill any http connection

            server.shutdown()
                .success(function () {
                    var options = {
                        title: "Shutdown",
                        body: "Flexget has been shutdown.",
                        ok: "Close"
                    }
                    Dialog.open(options);
                }).
                error(function (error) {
                    console.log("Error occured: " + error);
                    var options = {
                        title: "Shutdown failed",
                        body: "Oops, something went wrong: " + error.message,
                        ok: "Close"
                    }
                    Dialog.open(options);
                });
        };

        var shutdown = function () {
            var options = {
                title: "Confirm Shutdown",
                body: "Are you sure you want to shutdown Flexget?",
                ok: "Shutdown",
                cancel: "Cancel"
            }

            Dialog.open(options)
                .then(function(confirmed) {
                    doShutdown();
                }, function(error) {
                    
                });
        };

        toolBar.registerMenuItem('Manage', 'Reload', 'fa fa-refresh', reload);
        toolBar.registerMenuItem('Manage', 'Shutdown', 'fa fa-power-off', shutdown);

    }

})();
