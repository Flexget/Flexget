(function () {
  'use strict';

  angular.module('flexget.services')
    .factory('toolBar', function() {
      var items = [];
      var defaultOrder = 128;

      return {
        items: items,
        register: function(label, cssClass, action, order) {
          if (!order) {
            order = defaultOrder;
          }
          items.push({type: 'button', label: label, cssClass: cssClass, action: action, order: order});
        }
      }
    });

})();


