from __future__ import print_function
from builtins import object, str
from future import standard_library
from six import string_types

# external imports
import requests
import requests.auth
import time
from math import ceil
from requests import HTTPError

# package imports
from .utils import get_logger

logger = get_logger(__name__)


class ApiClient(object):
    """
    This class is used to make HTTP requests to the TruStar API.
    """

    def __init__(self, config=None):
        """
        Constructs and configures the instance.  Initially attempts to use ``config``; if it is ``None``,
        then attempts to use ``config_file`` instead.

        The only required config keys are ``user_api_key`` and ``user_api_secret``.  To obtain these values, login to
        TruSTAR Station in your browser and visit the **API** tab under **SETTINGS** to generate an API key and secret.

        All available keys, and their defaults, are listed below:

        +-------------------------+--------------------------------------------------------+
        | key                     | description                                            |
        +=========================+========================================================+
        | ``user_api_key``        | API key                                                |
        +-------------------------+--------------------------------------------------------+
        | ``user_api_secret``     | API secret                                             |
        +-------------------------+--------------------------------------------------------+
        | ``auth_endpoint``       | the URL used to obtain OAuth2 tokens                   |
        +-------------------------+--------------------------------------------------------+
        | ``api_endpoint``        | the base URL used for making API calls                 |
        +-------------------------+--------------------------------------------------------+
        | ``verify``              | whether to use SSL verification                        |
        +-------------------------+--------------------------------------------------------+
        | ``retry``               | whether to wait and retry requests that fail with 429  |
        +-------------------------+--------------------------------------------------------+
        | ``max_wait_time``       | allow to fail if 429 wait time is greater than this    |
        +-------------------------+--------------------------------------------------------+
        | ``client_type``         | the name of the client being used                      |
        +-------------------------+--------------------------------------------------------+
        | ``client_version``      | the version of the client being used                   |
        +-------------------------+--------------------------------------------------------+
        | ``client_metatag``      | any additional information (ex. email address of user) |
        +-------------------------+--------------------------------------------------------+

        :param dict config: A dictionary of configuration options.
        """

        # set properties
        self.auth = config.get('auth')
        self.base = config.get('base')
        self.api_key = config.get('api_key')
        self.api_secret = config.get('api_secret')
        self.client_type = config.get('client_type')
        self.client_version = config.get('client_version')
        self.client_metatag = config.get('client_metatag')
        self.verify = config.get('verify')
        self.retry = config.get('retry')
        self.max_wait_time = config.get('max_wait_time')

        # initialize token property
        self.token = None

    def _get_token(self):
        """
        Returns the token.  If no token has been generated yet, gets one first.
        :return: The OAuth2 token.
        """

        if self.token is None:
            self._refresh_token()
        return self.token

    def _refresh_token(self):
        """
        Retrieves the OAuth2 token generated by the user's API key and API secret.
        Sets the instance property 'token' to this new token.
        If the current token is still live, the server will simply return that.
        """

        # use basic auth with API key and secret
        client_auth = requests.auth.HTTPBasicAuth(self.api_key, self.api_secret)

        # make request
        post_data = {"grant_type": "client_credentials"}
        response = requests.post(self.auth, auth=client_auth, data=post_data)

        # raise exception if status code indicates an error
        if 400 <= response.status_code < 600:
            message = "{} {} Error: {}".format(response.status_code,
                                               "Client" if response.status_code < 500 else "Server",
                                               "unable to get token")
            raise HTTPError(message, response=response)

        # set token property to the received token
        self.token = response.json()["access_token"]

    def _get_headers(self, is_json=False):
        """
        Create headers dictionary for a request.

        :param boolean is_json: Whether the request body is a json.
        :return: The headers dictionary.
        """

        headers = {"Authorization": "Bearer " + self._get_token()}

        if self.client_type is not None:
            headers["Client-Type"] = self.client_type

        if self.client_version is not None:
            headers["Client-Version"] = self.client_version

        if self.client_metatag is not None:
            headers["Client-Metatag"] = self.client_metatag

        if is_json:
            headers['Content-Type'] = 'application/json'

        return headers

    @classmethod
    def _is_expired_token_response(cls, response):
        """
        Determine whether the given response indicates that the token is expired.

        :param response: The response object.
        :return: True if the response indicates that the token is expired.
        """

        EXPIRED_MESSAGE = "Expired oauth2 access token"
        INVALID_MESSAGE = "Invalid oauth2 access token"

        if response.status_code == 400:
            try:
                body = response.json()
                if str(body.get('error_description')) in [EXPIRED_MESSAGE, INVALID_MESSAGE]:
                    return True
            except:
                pass
        return False

    def request(self, method, path, headers=None, params=None, data=None, **kwargs):
        """
        A wrapper around ``requests.request`` that handles boilerplate code specific to TruStar's API.

        :param str method: The method of the request (``GET``, ``PUT``, ``POST``, or ``DELETE``)
        :param str path: The path of the request, i.e. the piece of the URL after the base URL
        :param dict headers: A dictionary of headers that will be merged with the base headers for the SDK
        :param kwargs: Any extra keyword arguments.  These will be forwarded to the call to ``requests.request``.
        :return: The response object.
        """

        retry = self.retry
        attempted = False
        while not attempted or retry:

            # get headers and merge with headers from method parameter if it exists
            base_headers = self._get_headers(is_json=method in ["POST", "PUT"])
            if headers is not None:
                base_headers.update(headers)

            # make request
            response = requests.request(method=method,
                                        url="{}/{}".format(self.base, path),
                                        headers=base_headers,
                                        verify=self.verify,
                                        params=params,
                                        data=data,
                                        **kwargs)

            attempted = True

            # refresh token if expired
            if self._is_expired_token_response(response):
                self._refresh_token()

            # if "too many requests" status code received, wait until next request will be allowed and retry
            elif retry and response.status_code == 429:
                wait_time = ceil(response.json().get('waitTime') / 1000)
                logger.debug("Waiting %d seconds until next request allowed." % wait_time)

                # if wait time exceeds max wait time, allow the exception to be thrown
                if wait_time <= self.max_wait_time:
                    time.sleep(wait_time)
                else:
                    retry = False

            # request cycle is complete
            else:
                retry = False

        # raise exception if status code indicates an error
        if 400 <= response.status_code < 600:

            # get response json body, if one exists
            resp_json = None
            try:
                resp_json = response.json()
            except:
                pass

            # get message from json body, if one exists
            if resp_json is not None and 'message' in resp_json:
                reason = resp_json['message']
            else:
                reason = "unknown cause"

            # construct error message
            message = "{} {} Error: {}".format(response.status_code,
                                               "Client" if response.status_code < 500 else "Server",
                                               reason)
            # raise HTTPError
            raise HTTPError(message, response=response)

        return response

    def get(self, path, params=None, **kwargs):
        """
        Convenience method for making ``GET`` calls.

        :param str path: The path of the request, i.e. the piece of the URL after the base URL.
        :param kwargs: Any extra keyword arguments.  These will be forwarded to the call to ``requests.request``.
        :return: The response object.
        """

        return self.request("GET", path, params=params, **kwargs)

    def put(self, path, params=None, data=None, **kwargs):
        """
        Convenience method for making ``PUT`` calls.

        :param str path: The path of the request, i.e. the piece of the URL after the base URL.
        :param kwargs: Any extra keyword arguments.  These will be forwarded to the call to ``requests.request``.
        :return: The response object.
        """

        return self.request("PUT", path, params=params, data=data, **kwargs)

    def post(self, path, params=None, data=None, **kwargs):
        """
        Convenience method for making ``POST`` calls.

        :param str path: The path of the request, i.e. the piece of the URL after the base URL.
        :param kwargs: Any extra keyword arguments.  These will be forwarded to the call to ``requests.request``.
        :return: The response object.
        """

        return self.request("POST", path, params=params, data=data, **kwargs)

    def delete(self, path, params=None, **kwargs):
        """
        Convenience method for making ``DELETE`` calls.

        :param str path: The path of the request, i.e. the piece of the URL after the base URL.
        :param kwargs: Any extra keyword arguments.  These will be forwarded to the call to ``requests.request``.
        :return: The response object.
        """

        return self.request("DELETE", path, params=params, **kwargs)
