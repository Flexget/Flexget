(function () {
  'use strict';

  angular.module('flexget.services')
    .provider('sideNav', function() {
      var items = [];

      this.register = function(href, caption, icon, order) {
        href = '/ui/#' + href;
        items.push({href: href, caption: caption, icon: icon, order: order})
      };

      this.$get = function() {
        return {
          items: items
        }
      };

    });

})();


