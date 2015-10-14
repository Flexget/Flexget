(function () {
  'use strict';

  angular.module('flexget.services')
    .factory('toolBar', function() {
      var items = [];
      var defaultOrder = 128;

      return {
        items: items,
        registerButton: function(label, cssClass, action, order) {
          if (!order) {
            order = defaultOrder;
          }
          items.push({type: 'button', label: label, cssClass: cssClass, action: action, order: order});
        },
        registerMenu: function(label, cssClass, menu, order) {
          if (!order) {
            order = defaultOrder;
          }
          items.push({type: 'menu', label: label, cssClass: cssClass, menu: menu, order: order});
        }
      }
    });

})();


