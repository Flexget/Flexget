/* eslint-disable no-unused-vars */
var mockStatesData = (function () {
	return {
		getStates: getStates
	};

	function getStates() {
		return [
			{
                name: 'flexget.home',
                url: '/',
                component: 'home'
			},
			{
				name: 'flexget.log',
				url: '/log',
				component: 'log',
				settings: {
					caption: 'Log',
					icon: 'file-text-o',
					weight: 1
				}
			},
			{
				name: 'flexget.movies',
				url: '/movies',
				components: 'moviesView',
				settings: {
					weight: 2,
					icon: 'tv',
					caption: 'Movies'
				}

			}
		];
	}
}());