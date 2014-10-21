import json
import requests
from requests.adapters import HTTPAdapter, DEFAULT_POOLSIZE

from app.util.decorators import retry_on_exception
from app.util.log import get_logger
from app.util.secret import Secret


ENCODED_BODY = '__encoded_body__'


class Network(object):
    """
    This is a wrapper around the requests library. This class contains things like logic to implement network retries,
    convenience methods for authenticated network calls, etc.
    """
    def __init__(self, min_connection_poolsize=DEFAULT_POOLSIZE):
        """
        :param min_connection_poolsize: The minimum connection pool size for this instance
        :type min_connection_poolsize: int
        """
        self._session = requests.Session()
        self._logger = get_logger(__name__)

        poolsize = max(min_connection_poolsize, DEFAULT_POOLSIZE)
        self._session.mount('http://', HTTPAdapter(pool_connections=poolsize, pool_maxsize=poolsize))

    def get(self, *args, **kwargs):
        """
        Send a GET request to a url. Arguments to this method, unless otherwise documented below in _request(), are
        exactly the same as arguments to session.get() in the requests library.

        :rtype: requests.Response
        """
        return self._request('GET', *args, **kwargs)

    # todo: may be a bad idea to retry -- what if post was successful but just had a response error?
    @retry_on_exception(exceptions=(requests.ConnectionError,))
    def post(self, *args, **kwargs):
        """
        Send a POST request to a url. Arguments to this method, unless otherwise documented below in _request(), are
        exactly the same as arguments to session.post() in the requests library.

        :rtype: requests.Response
        """
        return self._request('POST', *args, **kwargs)

    def post_with_digest(self, url, request_params, secret, error_on_failure=False):
        """
        Post to a url with the Message Authentication Digest
        :type url: str
        :type request_params: dict [str, str]
        :param secret: the secret used to produce the message auth digest
        :rtype: requests.Response
        """
        encoded_body = self.encode_body(request_params)
        return self.post(url, encoded_body, headers=Secret.header(encoded_body, secret),
                         error_on_failure=error_on_failure)

    def encode_body(self, body_decoded):
        """
        :type body_decoded: dict [str, str]
        :rtype: str
        """
        return json.dumps(body_decoded)

    def _request(self, method, url, data=None, should_encode_body=True, error_on_failure=False, *args, **kwargs):
        """
        A wrapper around requests library network request methods (e.g., GET, POST). We can add functionality for
        unimplemented request methods as needed. We also do some mutation on request bodies to make receiving data (in
        the Tornado request handlers) a bit more convenient.

        :param method: The request method -- passed through to requests lib
        :type method: str
        :param url: The request url -- passed through to requests lib
        :type url: str
        :param data: The request body data -- passed through to requests lib but may be mutated first
        :type data: dict|str|bytes|None
        :param should_encode_body: If True we json-encode the actual data inside a new dict, which is then sent with
            the request. This should be True for all Master<->Slave API calls but we can set this False to skip this
            extra encoding step if necessary.
        :type should_encode_body: bool
        :param error_on_failure: If true, raise an error when the response is not in the 200s
        :type error_on_failure: bool
        :rtype: requests.Response
        """

        # If data type is dict, we json-encode it and nest the encoded string inside a new dict. This prevents the
        # requests library from trying to directly urlencode the key value pairs of the original data, which will
        # not correctly encode anything in a nested dict. The inverse of this encoding is done on the receiving end in
        # ClusterBaseHandler. The reason we nest this in another dict instead of sending the json string directly is
        # that if files are included in a post request, the type of the data argument *must* be a dict.
        data_to_send = data
        if should_encode_body and type(data_to_send) is dict:
            data_to_send = {ENCODED_BODY: self.encode_body(data_to_send)}

        resp = self._session.request(method, url, data=data_to_send, *args, **kwargs)
        if not resp.ok and error_on_failure:
            raise _RequestFailedError('Request to {} failed with status_code {} and response "{}"'.
                                      format(url, str(resp.status_code), resp.text))
        return resp


class _RequestFailedError(Exception):
    pass