"""This module is a standalone client for the backend API. It is meant to keep the logic of the Telegram bot
separated from the backend interaction, to avoid tight coupling. The Telegram bot will only use the functions
of the `Backender` class, without being aware of what these functions are doing underneath.

Keep this in mind as you update this file: any function that starts with an underscore _ is not expected to be
invoked by the Telegram bot. All the other functions are assumed to be used by others, so make sure their
prototype is not changed unless there is a good reason.

The easiest way to work on this client is to run `python backend_api.py`, adjusting the contents after
`if __name__ == "__main__"` - this way you can test it without touching any Telegram functionality whatsoever."""

import logging
import base64

import requests

import constants as c

log = logging.getLogger("back")  # pylint: disable=invalid-name


class Backender:
    """This is a client that talks to the backend, transmitting information from the Telegram bot"""

    def __init__(self, url, username, password):
        """Initialize the backend REST API client"""
        self.base_url = url
        self.username = username
        self.password = password

    def _get(self, url):
        """Function for internal use, that sends GET requests to the server
        :param url: str, this will be added to the base_url to which the request is sent"""
        res = requests.get(self.base_url + url, auth=(self.username, self.password))
        # log.debug('Got %s', res.status_code)
        if res.status_code == 200:
            return res

        raise ValueError("Bad response")

    def _post(self, payload, url=""):
        """Function for internal use, it sends POST requests to the server
        :param payload: what needs to be sent within the POST request
        :param url: str, this will be added to the base_url to which the request is sent"""
        requests.post(self.base_url + url, auth=(self.username, self.password), json=payload)

    def _put(self, payload, url=""):
        """Function for internal use, it sends PUT requests to the server
        :param payload: what needs to be sent within the PUT request
        :param url: str, this will be added to the base_url to which the request is sent"""
        requests.put(self.base_url + url, auth=(self.username, self.password), json=payload)

    def get_request_details(self, request_id):
        """Retrieve the details of a request
        :param request_id: str, request id
        :returns: dict with the metadata"""
        response = self._get("beneficiary/filters/1/10?id=" + request_id)
        raw = response.json()

        # if there are no results, it means that such a request ID doesn't exist
        if raw["count"] == 0:
            raise KeyError

        # If we got this far, it means that the request exists and we can retrieve its details. Note that we
        # only take the first element, because we expect there to be a single request with that id
        return raw["list"][0]

    def link_chatid_to_volunteer(self, nickname, chat_id, phone):
        """Tell the backend that we've got a new bot user, along with their phone number, chat_id and nickname.
        :param nickname: optional str, Telegram nickname of the user, may be None if the nickname is not set
        :param chat_id: int, numerical chat_id that uniquely identifies the user's session with the bot in Telegram
        :param phone: str, phone number, full representation, e.g.:'+37379000000'
        :returns: bool, True if the user is known to the backend, otherwise False"""
        log.debug("Link vol:%s to chat %s and tel %s", nickname, chat_id, phone)
        response = self._get(url=f"volunteer?telegram_chat_id={chat_id}")
        return response.json()["exists"] if "exists" in response else False

    def register_pending_volunteer(self, data):
        """Tell the backend that we have a new volunteer who wants to help
        :param data: dict with the user profile details"""
        # Payload example
        # {'first_name', 'Alexei',
        #  'last_name', 'Murzicescu',
        #  'availability', '8',  # how many hours per day they can dedicate to the cause
        #  'activities', ['transport', 'delivery', 'phone'],
        #  'phone', '+3730000000'
        #  'chat_id' 12312323  # telegram chat id}
        # NOTE: optionally it will contain a `phoneEx` key, corresponding to a foreign phone number that their
        #       Telegram account was registered with
        log.debug(
            "Register chat_id=%s f_name=%s l_name=%s",
            data[c.PROFILE_CHAT_ID],
            data[c.PROFILE_FIRST_NAME],
            data[c.PROFILE_LAST_NAME],
        )
        self._post(payload=data, url="volunteer")

    # TODO
    def upload_shopping_receipt(self, data, request_id):
        """Upload a receipt to the server, to document expenses handled by the volunteer on behalf of the
        beneficiary. Note that it is possible that a volunteer will send several photos that are linked to the same
        request in the system.
        :param data: bytearray, raw data corresponding to the image
        :param request_id: str, identifier of request"""
        log.debug("Send receipt (%i bytes) for req:%s", len(data), request_id)
        payload = {"beneficiary_id": request_id, "data": base64.b64encode(data).decode()}
        self._post(payload=payload, url="receipt")

    def relay_offer(self, request_id, volunteer_id, offer):
        """Notify the server that an offer to handle a request was provided by a volunteer. Note that this function
        will be invoked multiple times for the same request, as soon as each volunteer will send their response.
        :param request_id: str, identifier of request
        :param volunteer_id: str, volunteer identifier
        :param offer: str, the offer indicates when the volunteer will be able to reach the beneficiary"""
        log.debug("Relay offer for req:%s from vol:%s -> %s (UTC)", request_id, volunteer_id, offer)
        payload = {
            "telegram_chat_id": volunteer_id,
            "offer_beneficiary_id": request_id,
            "availability_day": offer,
        }
        self._put(payload=payload, url="volunteer")

    def update_request_status(self, request_id, status):
        """Change the status of a request, e.g., when a volunteer is on their way, or when the request was fulfilled.
        :param request_id: str, identifier of request
        :param status: str, indicates what state it is in {new, onProgress, done, canceled}"""
        log.debug("Set req:%s to: `%s`", request_id, status)
        payload = {"_id": request_id, "status": status}
        self._put(payload=payload, url="beneficiary")

    def send_request_result(self, request_id, payload):
        """Send final request-related state info and findings (exit survey, symptoms, etc.) to the server.
        :param request_id: str, identifier of request
        :param payload: dict, see payload form in `ajubot.py/finalize_request`"""
        # TODO implement this
        log.debug("Set req:%s to: `%s`", request_id, payload)
        self._put(payload=payload, url="beneficiary")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.DEBUG, format="%(asctime)s %(levelname)5s %(name)5s - %(message)s"
    )

    # Here you can play around with the backend without involving any of the Telegram-related logic. Change these
    # credentials before running the demo
    url = "http://127.0.0.1:5000/api/"
    username = "testuser"
    password = "changethis"  # nosec

    b = Backender(url, username, password)
    result = b.get_request_details("5e84c10a9938cfffc0217ed1")
    log.info(result)
