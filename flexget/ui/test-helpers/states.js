var mockStatesData = (function () {
	return {
		getStates: getStates
	};

	function getStates() {
		return [
			{
                state: 'home',
                config: {
                    url: '/',
                    component: 'home'
                }
			},
			{
				state: 'log',
				config: {
					url: '/log',
					component: 'logView',
					settings: {
						weight: 1,
						icon: 'file-text-o',
						caption: 'Log'
					}
				}
			},
			{
				state: 'movies',
				config: {
					url: '/movies',
					components: 'moviesView',
					settings: {
						weight: 2,
						icon: 'tv',
						caption: 'Movies'
					}
				}
			}
		]
	}
})();