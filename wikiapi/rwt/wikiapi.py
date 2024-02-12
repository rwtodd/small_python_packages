"""A module to facilitate uploading files and articles to a mediawiki.
It depends on the `requests` module."""

__all__ = [ 'WikiSession' ]

import requests
import os

_IMAGE_EXTS = { '.png', '.gif', '.jpg', '.jpeg' }

class WikiSession:
    def __enter__(self):
        """Nothing todo when entering a context manager"""
        return self

    def __exit__(self, exc_type, exc_value, exc_tb):
        """Log out if we haven't already, when leaving the context"""
        self.logout()

    def __init__(self, url):
        """Create a session for api endpoint `url`.
        It should be the api.php address."""
        self._url = url
        self._logged_in = False
        self._session = requests.Session()

    def login(self, uname, pw):
        """Log into the mediawiki with credentials `uname` and `pw`, 
        and get a token needed for uploads"""
        params = { "action": "query", "meta": "tokens", 
                    "type": "login", "format": "json" }
        response = self._session.get(url=self._url, params=params)
        data = response.json()
        login_token = data['query']['tokens']['logintoken']

        # Step 2: POST the login request
        params = { "action": "login", "lgname": uname,
                  "lgpassword": pw, "lgtoken": login_token,
                  "format": "json" }
        response = self._session.post(url=self._url, data=params)

        # Step 3: GET request to fetch CSRF token
        params = { "action": "query", "meta": "tokens", "format": "json" }
        response = self._session.get(url=self._url, params=params)
        data = response.json()
        self._csrf_token = data['query']['tokens']['csrftoken']
        self._logged_in = True
        return response 

    def logout(self):
        """Log out of the mediawiki, if logged in"""
        # https://www.mediawiki.org/wiki/API:Logout
        if not self._logged_in: return
        params = { "action": "logout", "token": self._csrf_token, "format": "json" }
        response = self._session.post(url=self._url, data=params)
        self._logged_in = False
        self._csrf_token = None
        return response

    def edit_from_file(self, filename, comment, title=None, action='text'):
        """Edit a mediawiki text from `filename`. If the title isn't given, it
        is derived from the filename. `action` defaults to 'text', but can also
        be 'appendtext' or 'prependtext'"""
        # https://www.mediawiki.org/wiki/API:Edit
        if not self._logged_in:
            raise RuntimeError("Not logged in to the mediawiki.")

        basename = os.path.basename(filename)
        base, ext = os.path.splitext(basename)
        if ext.lower() in _IMAGE_EXTS:
            raise RuntimeError(f"Sending image file <{filename}> as an article!")

        if title is None:
            title = base.replace('_',' ')

        with open(filename, 'rb') as f:
            return self.edit_from_string(title, f.read(), comment, action)

    def edit_from_string(self, title, text, comment, action='text'):
        """Edit a mediawiki text for article with `title`, giving it `text`, 
        with a summary of `comment`.  Returns the response."""
        # https://www.mediawiki.org/wiki/API:Edit
        if not self._logged_in:
            raise RuntimeError("Not logged in to the mediawiki.")
        params = { "action": "edit", "title": title,
                  "token": self._csrf_token, "format": "json",
                  action: text, "summary": comment }
        response = self._session.post(url=self._url, data=params)
        return response

    def upload_from_file(self, filename, comment, title=None):
        """Upload a file (e.g., Image) to the wiki"""
        # https://www.mediawiki.org/wiki/API:Upload
        if not self._logged_in:
            raise RuntimeError("Not logged in to the mediawiki.")
        basename = os.path.basename(filename)
        base, ext = os.path.splitext(basename)
        if ext.lower() not in _IMAGE_EXTS:
            raise RuntimeError(f"Trying to upload a non-image file <{filename}>!")
        if title is None:
            title = basename.replace('_',' ')
        with open(filename, 'rb') as f:
            params = { "action": "upload", "filename": title,
                      "format": "json", "token": self._csrf_token,
                      "ignorewarnings": 1 }
            file = {'file': (title, f, 'multipart/form-data')}
            response = self._session.post(url=self._url, files=file, data=params)
            return  response

    def fetch_wikitext(self, title):
        """Fetch the wikitext of an article. Returns the full json response, as well as the
        wikitext (even though the wikitext is embedded in the response)"""
        # https://www.mediawiki.org/wiki/API:Get_the_contents_of_a_page
        if not self._logged_in:
            raise RuntimeError("Not logged in to the mediawiki.")
        params = {
            'action': 'parse',
            'page': title,
            'prop': 'wikitext',
            'format': 'json'
        }
        response = self._session.get(url=self._url, params=params)
        data = response.json()
        wikitext = data['parse']['wikitext']['*']
        return (response, wikitext)

    def fetch_html(self, title):
        """Fetch the html of an article. Returns the full json response, as well as the
        wikitext (even though the wikitext is embedded in the response)"""
        # https://www.mediawiki.org/wiki/API:Get_the_contents_of_a_page
        if not self._logged_in:
            raise RuntimeError("Not logged in to the mediawiki.")
        params = {
            'action': 'parse',
            'page': title,
            'prop': 'text',
            'format': 'json'
        }
        response = self._session.get(url=self._url, params=params)
        data = response.json()
        html = data['parse']['text']['*']
        return (response, html)

