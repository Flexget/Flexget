describe("Service: Login", function () {
	beforeEach(function () {
		bard.appModule('components.auth');

		bard.inject('$httpBackend', 'authService', 'exception', '$q');

		sinon.stub(exception, 'catcher').returns($q.reject({ message: "Request failed" }));
	});

	it("should exist", function () {
		expect(authService).to.exist;
	});

	describe('getLists()', function () {
		it("should issue a GET /api/auth/logout/ request", function () {
			$httpBackend.expect('GET', '/api/auth/logout/').respond(200, {});
			authService.logout().then(function () {
				expect(true).to.be.true;
			});
			$httpBackend.flush();
		});

		it("should report an error if request fails", function () {
			$httpBackend.expect('GET', '/api/auth/logout/').respond(500);
			authService.logout().catch(function (error) {
				expect(error.message).to.equal("Request failed");
				expect(exception.catcher).to.have.been.calledOnce;
			});
			$httpBackend.flush();
		});
	});

	describe('login()', function () {
		it('should issue a POST /api/auth/login/ request', function () {
			$httpBackend.expect('POST', '/api/auth/login/?remember=false').respond(200, {});

			var credentials = {
				username: "flexget",
				password: 'password'
			};
				
			authService.login().then(function (data) {
				expect(true).to.be.true;
			});
			$httpBackend.flush();
		});

		it('should reject when an error occurs', function () {
			$httpBackend.expect('POST', '/api/auth/login/?remember=false').respond(500, {});

			var credentials = {
				username: "flexget",
				password: 'password'
			};
				
			authService.login().catch(function (data) {
				expect(data).to.exist;
			});
			$httpBackend.flush();
		});
	});
});