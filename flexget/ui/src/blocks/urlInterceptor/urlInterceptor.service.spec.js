describe("Blocks: UrlInterceptor", function () {
	beforeEach(function () {
		bard.appModule('blocks.urlInterceptor');

		bard.inject('urlInterceptor', '$httpBackend');

		//sinon.spy(exception, 'catcher');
	});

	it("should exist", function () {
		expect(urlInterceptor).to.exist;
	});

	describe('request()', function () {
		it("should exist", function () {
			expect(urlInterceptor.request).to.exist;
		});

		it('should append a trailing slash to the request', function () {
			var config = urlInterceptor.request({ url: '/api/movie_list' });

			expect(config.url).to.equal('/api/movie_list/');
		});

		it('should not append a trailing slash when one is present already', function () {
			var config = urlInterceptor.request({ url: '/api/movie_list/' });

			expect(config.url).to.equal('/api/movie_list/');
		});

		it('should not append a trailing slash to resource requests', function () {
			var config = urlInterceptor.request({ url: '/movies.tmpl.html' });

			expect(config.url).to.equal('/movies.tmpl.html');
		});
	});
});