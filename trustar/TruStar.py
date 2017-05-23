from __future__ import print_function

from future import standard_library

standard_library.install_aliases()

import configparser, json
from builtins import object
from datetime import datetime
from tzlocal import get_localzone

import pytz
import sys
import requests
import requests.auth
import dateutil
import time

import pdfminer.pdfinterp
from pdfminer.pdfpage import PDFPage
from pdfminer.converter import TextConverter
from pdfminer.layout import LAParams
from cStringIO import StringIO


class TruStar(object):
    """
    Main class you to instantiate the TruStar API
    """

    def __init__(self, config_file="trustar.conf", config_role="integration"):

        self.enclaveIds = []
        self.attributedToMe = False

        config_parser = configparser.RawConfigParser()
        config_parser.read(config_file)

        try:
            # parse required properties
            self.auth = config_parser.get(config_role, 'auth_endpoint')
            self.base = config_parser.get(config_role, 'api_endpoint')
            self.apikey = config_parser.get(config_role, 'user_api_key')
            self.apisecret = config_parser.get(config_role, 'user_api_secret')

            # parse enclave an attribution properties
            if config_parser.has_option(config_role, 'enclave_ids'):
                self.enclaveIds = filter(None, config_parser.get(config_role, 'enclave_ids').split(','))

            if config_parser.has_option(config_role, 'attribute_reports'):
                self.attributedToMe = config_parser.getboolean(config_role, 'attribute_reports')
        except Exception as e:
            print("Problem reading config file: %s", e)
            sys.exit(1)

    @staticmethod
    def normalize_timestamp(date_time):
        """
        Attempt to convert a string timestamp in to a TruSTAR compatible format for submission.
        Will return current time with UTC time zone if None
        :param date_time: int that is epoch time, or string/datetime object containing date, time, and ideally timezone
        examples of supported timestamp formats: 1487890914, 1487890914000, "2017-02-23T23:01:54", "2017-02-23T23:01:54+0000"
        """
        datetime_dt = datetime.now()

        # get current time in seconds-since-epoch
        current_time = int(time.time())

        try:
            # identify type of timestamp and convert to datetime object
            if isinstance(date_time, int):

                # if timestamp has more than 10 digits, it is in ms
                if date_time > 9999999999:
                    date_time /= 1000

                # if timestamp is incorrectly forward dated, set to current time
                if date_time > current_time:
                    date_time = current_time
                datetime_dt = datetime.fromtimestamp(date_time)
            elif isinstance(date_time, str):
                datetime_dt = dateutil.parser.parse(date_time)
            elif isinstance(date_time, datetime):
                datetime_dt = date_time

        # if timestamp is none of the formats above, error message is printed and timestamp is set to current time by default
        except Exception as e:
            print(e)
            datetime_dt = datetime.now()

        # if timestamp is timezone naive, add timezone
        if not datetime_dt.tzinfo:
            timezone = get_localzone()

            # add system timezone
            datetime_dt = timezone.localize(datetime_dt)

            # convert to UTC
            datetime_dt = datetime_dt.astimezone(pytz.utc)

        # converts datetime to iso8601
        return datetime_dt.isoformat()

    def get_token(self, verify=True):
        """
        Retrieves the OAUTH token generated by your API key and API secret.
        this function has to be called before any API calls can be made
        :param verify: boolean - ignore verifying the SSL certificate if you set verify to False
        """
        client_auth = requests.auth.HTTPBasicAuth(self.apikey, self.apisecret)
        post_data = {"grant_type": "client_credentials"}
        resp = requests.post(self.auth, auth=client_auth, data=post_data, verify=verify)
        token_json = resp.json()
        return token_json["access_token"]

    def get_latest_reports(self, access_token):
        """
        Retrieves the latest 5 reports submitted to the TruSTAR community
        :param access_token: OAuth API token
        """

        headers = {"Authorization": "Bearer " + access_token}
        resp = requests.get(self.base + "/reports/latest", headers=headers)
        return json.loads(resp.content.decode('utf8'))

    def get_report_details(self, access_token, report_id, id_type="internal"):
        """
        Retrieves the report details
        :param access_token: OAuth API token
        :param report_id: Incident Report ID
        """

        headers = {"Authorization": "Bearer " + access_token}
        payload = {'id': report_id, 'id_type': id_type}
        resp = requests.get(self.base + "/report", payload, headers=headers)
        return json.loads(resp.content)

    def update_report(self, access_token, report_id, id_type, body):
        """
        Retrieves the report details
        :param access_token: OAuth API token
        :param report_id: Incident Report ID
        """

        headers = {'Authorization': 'Bearer ' + access_token, 'content-Type': 'application/json'}
        params = {'id': report_id, 'id_type': id_type}
        payload = body
        resp = requests.put(self.base + "/report", json.dumps(payload, encoding="ISO-8859-1"), params=params, headers=headers)
        return json.loads(resp.content)

    def delete_report(self, access_token, report_id, id_type="internal"):
        """
        Retrieves the report details
        :param access_token: OAuth API token
        :param report_id: Incident Report ID
        """

        headers = {"Authorization": "Bearer " + access_token}
        payload = {'id': report_id, 'id_type': id_type}
        resp = requests.delete(self.base + "/report", payload, headers=headers)
        return json.loads(resp.content)

    def get_correlated_reports(self, access_token, indicator):
        """
        Retrieves all TruSTAR reports that contain the searched indicator. You can specify multiple indicators
        separated by commas
        :param indicator:
        :param access_token:
        """

        headers = {"Authorization": "Bearer " + access_token}
        payload = {'q': indicator}
        resp = requests.get(self.base + "/reports/correlate", payload, headers=headers)
        return json.loads(resp.content)

    def query_indicators(self, access_token, indicators, limit):
        """
        Finds all reports that contain the indicators and returns correlated indicators from those reports.
        you can specify the limit of indicators returned.
        :param limit: max number of results to return
        :param indicators: list of space-separated indicators to search for
        :param access_token:
        """

        headers = {"Authorization": "Bearer " + access_token}
        payload = {'q': indicators, 'limit': limit}

        resp = requests.get(self.base + "/indicators", payload, headers=headers)
        return json.loads(resp.content)

    def query_latest_indicators(self,
                                access_token,
                                source,
                                indicator_types,
                                limit,
                                interval_size):
        """
        Finds all latest indicators
        :param access_token: OAUTH access token
        :param source: source of the indicators which can either be INCIDENT_REPORT or OSINT
        :param interval_size: time interval on returned indicators. Max is set to 24 hours
        :param limit: limit on the number of indicators. Max is set to 5000
        :param indicator_types: a list of indicators or a string equal to "ALL" to query all indicator types extracted
        by TruSTAR
        :return json response of the result
        """

        headers = {"Authorization": "Bearer " + access_token}
        payload = {'source': source, 'types': indicator_types, 'limit': limit, 'intervalSize': interval_size}
        resp = requests.get(self.base + "/indicators/latest", payload, headers=headers)
        return json.loads(resp.content)

    def submit_report(self, access_token, external_id, report_body_txt, report_name, began_time=datetime.now(),
                      enclave=False, verify=True):
        """
        Wraps supplied text as a JSON-formatted TruSTAR Incident Report and submits it to TruSTAR Station
        By default, this submits to the TruSTAR community. To submit to your enclave, pass in your enclave_id
        :param began_time:
        :param enclave: boolean - whether or not to submit report to user's enclaves (see 'enclave_ids' config property)
        :param report_name:
        :param report_body_txt:
        :param access_token:
        :param verify: boolean - ignore verifying the SSL certificate if you set verify to False
        """

        # Convert timestamps
        distribution_type = 'ENCLAVE' if enclave else 'COMMUNITY'
        if distribution_type == 'ENCLAVE' and len(self.enclaveIds) < 1:
            raise Exception("Must specify one or more enclave IDs to submit enclave reports into")

        headers = {'Authorization': 'Bearer ' + access_token, 'content-Type': 'application/json'}

        payload = {'incidentReport': {
            'title': report_name,
            'externalTrackingId': external_id,
            'timeBegan': self.normalize_timestamp(began_time),
            'reportBody': report_body_txt,
            'distributionType': distribution_type},
            'enclaveIds': self.enclaveIds,
            'attributedToMe': self.attributedToMe}
        print("Submitting report %s to TruSTAR Station..." % report_name)
        resp = requests.post(self.base + "/report", json.dumps(payload, encoding="ISO-8859-1"), headers=headers,
                             timeout=60, verify=verify)

        return resp.json()

    @staticmethod
    def extract_pdf(file_name):
        rsrcmgr = pdfminer.pdfinterp.PDFResourceManager()
        sio = StringIO()
        laparams = LAParams()
        device = TextConverter(rsrcmgr, sio, codec='utf-8', laparams=laparams)
        interpreter = pdfminer.pdfinterp.PDFPageInterpreter(rsrcmgr, device)

        # Extract text from pdf file
        fp = file(file_name, 'rb')
        for page in PDFPage.get_pages(fp, maxpages=20):
            interpreter.process_page(page)
        fp.close()

        text = sio.getvalue()

        # Cleanup
        device.close()
        sio.close()

        return text

    @staticmethod
    def process_file(source_file):
        if source_file.endswith(('.pdf', '.PDF')):
            txt = TruStar.extract_pdf(source_file)
        elif source_file.endswith(('.txt', '.eml', '.csv', '.json')):
            f = open(source_file, 'r')
            txt = f.read()
        else:
            raise ValueError('UNSUPPORTED FILE EXTENSION')
        return txt

    def get_report_url(self, report_id):
        """
        Build direct URL to report from its ID
        :param report_id: Incident Report (IR) ID, e.g., as returned from `submit_report`
        :return URL
        """

        # Check environment for URL
        base_url = 'https://station.trustar.co' if ('https://api.trustar.co' in self.base) else \
            self.base.split('/api/')[0]

        return "%s/constellation/reports/%s" % (base_url, report_id)
