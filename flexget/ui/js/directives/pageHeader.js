'use strict';

app.directive('pageHeader', function() {
  return {
      restrict: 'AE',
      replace: 'true',
      template: '<section class="content-header"><h1>{{title }}<small>{{ description }}</small></h1></section>'
  };
});

