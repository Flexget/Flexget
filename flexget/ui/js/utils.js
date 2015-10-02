'use strict';

String.prototype.startsWith = function(prefix) {
  return this.indexOf(prefix) === 0;
};

function registerFlexModule(module) {
  angular.module('flexgetApp').requires.push(module.name);
}

app.menu = [];
app.routes = [];

function register_menu(href, caption, icon, order) {
  href = '/ui/#' + href;
  app.menu.push({href: href, caption: caption, icon: icon, order: order})
}

function register_route(name, url, controller, template) {
  app.routes.push({
    name: name,
    url: url,
    controller: controller,
    template: template
  });
}