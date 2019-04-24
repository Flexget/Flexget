from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

from os import environ
import logging
from http.cookiejar import CookieJar, Cookie

from flexget import plugin
from flexget.event import event
from pprint import pformat

log = logging.getLogger('selenium')


class title_is_not(object):
    '''
    Helper class for WebDriverWait
    An expectation for checking the title of a page.
    Title is not the given title
    returns True if the title does not match, false otherwise.
    '''

    def __init__(self, title):
        self.title = title

    def __call__(self, driver):
        return self.title != driver.title


class Selenium(object):
    '''
    #Selenium: helper plugin for cloudflare DDOS protection and website logins
    The selenium plugin uses the browser-automation framework selenium to emulate an actual browser interaction with
    certain websites. This helps to circumvent cloudflare DDOS protection and certain complicated login procedures.

    ## Configuration

    Currently, the following actions are supported:
    1. `cloudflare_ddos`: circumvent cloudflare protection. Parameters: 'url`: url to page that is protected by cloudflare
    2. `imdb_login`: log in to imdb. So that the rest of the task can be performed as logged in user. Parameters: `username`: email used for login, `password`: password used for login.
    3. `login`: log in to arbirtrary page. Parameters: `url`: url to login page, `username`: user name (or email) used for login, `password`: password used for login, `input_username_id`: id tag of field where username (or email) is to be entered, `input_password_id`: id tag of field where password is to be entered, `login_button_id`: id tag of button that must be clicked in order to log in, `element_after_login_id`: id of an element that appears on the page only after login, used to wait for successful loading of the page after login.

    **Configuration example for cloudflare DDOS protection:**
    ```yaml
    selenium:
      action: cloudflare_ddos
      parameters:
        url: http://example.com
    ```

    **Configuration example for imdb login**
    ```yaml
    selenium:
      action: imdb_login
      parameters:
        username: me@example.com
        password: YouWon'tGuess
    ```

    **Configuration example for general login**
    ```yaml
    selenium:
      action: login
      parameters:
        url: http://example.com/login
        username: MyName
        password: YouWon'tGuess
        input_username_id: username_input_field_id
        input_password_id: password_input_field_id
        login_button_id: button_id
        element_after_login_id: logout_button_id
    ```

    **Configuring the selenium browser backend via environment variables**
    The selenium backend is configured via environment variables, which makes it possible to easily configure it within
    docker containers and to have flexget and the browser run in different containers.
    ```bash
    SELENIUM_REMOTE_URL=http://geckodriver-alpine:4444 # host where the remote driver is running.
    SELENIUM_BROWSER=<firefox (default) | chrome> # this can be used to configure which driver to use (either locally or remotely if SELENIUM_REMOTE_URL is set).
    ```

    ## Requirements
    Needs the selenium python module `pip install selenium`.
    Also needs geckodriver and firefox installed on the same machine or running within a dockerimage.
    I am using the following `docker-compose.yml` file:
    ```yaml
    version: "3"
    services:
      docker-flexget:
        image: docker-flexget:latest #this is a self-generated image that contains the python selenium package
        restart: unless-stopped
        volumes:
          - /home/<user>/.flexget:/config
        environment:
          - TZ=Europe/Berlin
          - SELENIUM_REMOTE_URL=http://selenium:4444/wd/hub
          - PUID=1000
          - PGID=1000
        depends_on:
          - selenium
        ports:
          - 3539:3539
    
      selenium:
        image: selenium/standalone-firefox
        restart: unless-stopped
        volumes:
          - /dev/shm:/dev/shm
        environment:
          - TZ=Europe/Berlin
        ports:
          - 4444:4444
    ```
    '''
    schema = {
        'type': 'object',
        'properties': {'chromedriver': {'type': 'string'}, 'action': {'type': 'string'}, 'parameters': {'type': 'object'}},
        'additionalProperties': False,
    }

    config = {}

    implemented_actions = ['cloudflare_ddos', 'login', 'imdb_login']

    cj = CookieJar()

    @plugin.priority(253)
    def on_task_start(self, task, config):
        '''
        Constructor
        @param task: the flexget task object
        @param config: the configuration for the selenium plugin
        '''
        try:
            from selenium import webdriver
            from selenium.webdriver.support.ui import WebDriverWait
            from selenium.common.exceptions import WebDriverException
        except ImportError as e:
            log.error('Error importing selenium: %s' % e)
            raise plugin.DependencyError(
                'selenium', 'selenium', 'Selenium module required. run "pip install selenium". Also needs chromedriver and chromium (for example in Alpine Linux run: "apk add chromium chromium-chromedriver"). ImportError: %s' % e)
        self.config.update(config)
        use_firefox = True
        if 'SELENIUM_BROWSER' in environ and 'chrom' in environ['SELENIUM_BROWSER'].lower():
            use_firefox = False
        try:
            if use_firefox:
                options = webdriver.FirefoxOptions()
                options.headless = True
            else:
                options = webdriver.ChromeOptions()
                options.add_argument('headless')
                options.add_argument('disable-gpu')
                options.add_argument('no-sandbox')
                options.add_argument(
                    'user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_13_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/73.0.3683.75 Safari/537.36')
            if 'SELENIUM_REMOTE_URL' in environ:
                self.driver = webdriver.Remote(command_executor=environ['SELENIUM_REMOTE_URL'],
                                               desired_capabilities=options.to_capabilities())
            else:
                if use_firefox:
                    self.driver = webdriver.Firefox(firefox_options=options)
                else:
                    self.driver = webdriver.Chrome(chrome_options=options)
        except WebDriverException as e:
            raise plugin.DependencyError(
                'selenium', 'selenium', 'Selenium could not connect to a driver. Check whether the proper driver (SELENIUM_BROWSER) is installed and in your PATH or whether the remote host (SELENIUM_REMOTE_HOST) and port (SELENIUM_REMOTE_PORT) are properly configured. WebDriverException: %s' % e)

        self.wait = WebDriverWait(self.driver, 10)
        if config['action'] in self.implemented_actions:
            implemented_action = getattr(self, config['action'])
            implemented_action(task, self.config['parameters'])
        else:
            log.debug('The selenium plugin does not support this action: %s. Allowed values for the "action" config parameter are: %s' %
                      config['action'], self.implemented_actions)

    def __del__(self):
        '''
        Before destroying the class object, we need to close the Selenium driver.
        '''
        self.driver.quit()

    def add_selenium_cookie(self, cookie):
        '''
        Adds a cookie obtained by selenium to the cookiejar.
        @param cookie:  a cookie object returned by selenium driver.get_cookie()
        '''
        log.debug('Added cookie: %s' % pformat(cookie))
        default_attributes = ['name', 'value', 'secure', 'discard', 'comment', 'comment_url']
        cookie_attributes = {'domain': None, 'domain_specified': False, 'domain_initial_dot': False,
                             'path': None, 'path_specified': False, 'port': None, 'port_specified': False, 'expires': None}
        if cookie:
            if 'domain' in cookie:
                cookie_attributes['domain'] = cookie['domain']
                cookie_attributes['domain_specified'] = True
                cookie_attributes['domain_initial_dot'] = cookie['domain'][0] == '.'
                del cookie['domain']
            if 'path' in cookie:
                cookie_attributes['path'] = cookie['path']
                cookie_attributes['path_specified'] = True
                del cookie['path']
            if 'port' in cookie:
                cookie_attributes['port'] = cookie['port']
                cookie_attributes['port_specified'] = True
                del cookie['port']
            if 'expiry' in cookie:
                cookie_attributes['expires'] = cookie['expiry']
                del cookie['expiry']
            for attribute in default_attributes:
                if attribute in cookie:
                    cookie_attributes[attribute] = cookie[attribute]
                    del cookie[attribute]
                else:
                    cookie_attributes[attribute] = None
            if cookie:
                cookie_attributes['rest'] = cookie
            html_cookie = Cookie(version=0, name=cookie_attributes['name'], value=cookie_attributes['value'], domain=cookie_attributes['domain'], domain_specified=cookie_attributes['domain_specified'], domain_initial_dot=cookie_attributes['domain_initial_dot'], secure=cookie_attributes['secure'], path=cookie_attributes['path'],
                                 path_specified=cookie_attributes['path_specified'], port=cookie_attributes['port'], port_specified=cookie_attributes['port_specified'], expires=cookie_attributes['expires'], discard=cookie_attributes['discard'], comment=cookie_attributes['comment'], comment_url=cookie_attributes['comment_url'], rest=cookie_attributes['rest'])
            self.cj.set_cookie(html_cookie)

    def cloudflare_ddos(self, task, parameters):
        '''
        circumvent cloudflares ddos protection by accessing the site via a browser, waiting until the browser test has
        passed and copying the cookies to the task.requests session.
        @param task: the task object of the currently running task.
        @param parameters: the parametes config dict object should contain the url of the page to be accessed
        '''
        from selenium.common.exceptions import TimeoutException
        self.driver.get(parameters['url'])
        try:
            self.wait.until(title_is_not('Just a moment...'))
            log.verbose('Passed cloudflare DDOS protection for url: "%s". Page title is now: %s',
                        parameters['url'], self.driver.title)
        except TimeoutException:
            log.warning('Could not circumvent cloudflare protection for url: "%s". Page title is now: %s',
                        parameters['url'], self.driver.title)

        user_agent = self.driver.execute_script("return navigator.userAgent;")
        self.add_selenium_cookie(self.driver.get_cookie('__cfduid'))
        self.add_selenium_cookie(self.driver.get_cookie('cf_clearance'))
        # copy the obtained cookies to flexgets general requests session used by other plugins
        task.requests.add_cookiejar(self.cj)
        # update the header of flexgets requests session to match the header used to circumvent cloudflare
        task.requests.headers.update({'User-Agent': user_agent})
        log.debug('Cookies now stored in task.requests.cookies: %s' % pformat(task.requests.cookies))
        self.driver.quit()

    def login(self, task, parameters):
        '''
        Use selenium to log in to an arbirtrary page. Copy all session cookies to the task.requests session so that the
        user is logged in for the remainder of the task.
        @param task: the task object of the currently running task.
        @param parameters: The parameters config dict object should contain: `url`: url to login page, `username`: user name (or email) used for login, `password`: password used for login, `input_username_id`: id tag of field where username (or email) is to be entered, `input_password_id`: id tag of field where password is to be entered, `login_button_id`: id tag of button that must be clicked in order to log in, `element_after_login_id`: id of an element that appears on the page only after login, used to wait for successful loading of the page after login.
        '''
        import selenium.webdriver.support.expected_conditions as EC
        from selenium.webdriver.common.by import By
        from selenium.common.exceptions import TimeoutException
        self.driver.get(parameters['url'])
        input_email = self.driver.find_element_by_id(parameters['input_username_id'])
        input_email.send_keys(parameters['username'])
        input_password = self.driver.find_element_by_id(parameters['input_password_id'])
        input_password.send_keys(parameters['password'])
        login_button = self.driver.find_element_by_id(parameters['login_button_id'])
        login_button.click()
        try:
            self.wait.until(EC.presence_of_element_located((By.ID, parameters['element_after_login_id'])))
        except TimeoutException:
            log.warning('Could not verify the presence of an element with the id "%s". Login may have failed.' %
                        parameters['element_after_login_id'])
        log.verbose('Logged in at url: "%s". Page title is now: %s', parameters['url'], self.driver.title)
        for cookie in self.driver.get_cookies():
            self.add_selenium_cookie(cookie)
        # copy the obtained cookies to flexgets general requests session used by other plugins
        task.requests.add_cookiejar(self.cj)
        self.driver.quit()

    def imdb_login(self, task, parameters):
        '''
        Use selenium to log in to imdb. Copy all session cookies to the task.requests session so that the user is logged in for the remainder of the task.
        @param task: the task object of the currently running task.
        @param parameters: The parameters config dict object should contain: `username`: email used for login, `password`: password used for login
        '''
        self.driver.get(
            'https://www.imdb.com/registration/signin?u=https%3A//www.imdb.com/%3Fref_%3Dlgn_login&ref_=nv_generic_lgin')
        login_link = self.driver.find_element_by_partial_link_text('Sign in with IMDb')
        parameters['url'] = login_link.get_attribute("href")
        parameters['input_username_id'] = 'ap_email'
        parameters['input_password_id'] = 'ap_password'
        parameters['login_button_id'] = 'signInSubmit'
        parameters['element_after_login_id'] = 'nblogout'
        self.login(task, parameters)


@event('plugin.register')
def register_plugin():
    plugin.register(Selenium, 'selenium', api_ver=2)
