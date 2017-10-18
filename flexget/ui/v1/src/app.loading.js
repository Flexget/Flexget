'use strict';

window.loadingScreen = window.pleaseWait({
        logo: 'assets/images/header.png',
        backgroundColor: '#FFFFFF',
        loadingHtml: '' +
        '<p class="text-primary text-bold">Loading</p>' +
        '<div class="spinner">' +
        '<div class="rect1"></div><div class="rect2"></div><div class="rect3"></div>' +
        '<div class="rect4"></div><div class="rect5"></div>' +
        '</div>'
});