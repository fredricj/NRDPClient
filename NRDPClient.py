#!/usr/bin/env python3

# MIT License
#
# Copyright (c) 2017 Fredric Johansson
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import xml.etree.ElementTree as ET
import argparse
import requests
from urllib.parse import urlparse
import re
import sys


class NRDPClient:
    url = ""
    token = ""

    def __init__(self, url, token):
        urlparse(url)
        self.token = token
        self.url = url

    def run(self, args):
        xml = self.generate_xml(args)
        try:
            response = self.send(xml)
        except Exception as e:
            print("Connection Error occurred: {}".format(str(e),))
            return 1
        try:
            count = self.parse_response(response)
        except Exception as e:
            print("Failed to parse response: {}".format(str(e),))
            return 1
        if count > 0:
            return 0
        else:
            return 2

    def generate_xml(self, data):
        checktype = data.checktype
        hostname = data.hostname
        servicename = data.service
        state = data.state
        output_text = data.output

        checkresults_tag = ET.Element('checkresults')
        checkresult_tag = ET.SubElement(checkresults_tag, 'checkresult')
        # cr.set('type', 'service')
        if data.service:
            checkresult_tag.set('type', 'service')
        checkresult_tag.set('checktype', checktype)
        hostname_tag = ET.SubElement(checkresult_tag, 'hostname')
        hostname_tag.text = hostname
        if data.service:
            servicename_tag = ET.SubElement(checkresult_tag, 'servicename')
            servicename_tag.text = servicename
        else:
            checkresult_tag.set('type', 'host')
        state_tag = ET.SubElement(checkresult_tag, 'state')
        state_tag.text = state
        output_tag = ET.SubElement(checkresult_tag, 'output')
        output_tag.text = output_text
        return ET.tostring(checkresults_tag, method='xml')

    def send(self, xml):
        """ Sends the service/host check to a remote NRDP server """
        try:
            response = requests.post(self.url, data={'token': self.token, 'cmd': 'submitcheck', 'XMLDATA': xml},
                                     timeout=5)
        except requests.exceptions.Timeout as e:
            raise Exception("Request timed out") from e
        except requests.exceptions.ConnectionError as e:
            raise Exception("Failed to connect to server, network error: {}".format(e,)) from e
        except requests.exceptions.RequestException as e:
            raise Exception("Failed to connect to server: {}".format(e,)) from e
        if response.ok:
            return response
        else:
            raise RuntimeError

    def parse_response(self, response):
        root = ET.fromstring(response.text)
        status = root.find('./status')
        if status is None:
            raise Exception("Failed to get status from response")
        match = re.match("^\d+$", status.text)
        if match is None:
            raise Exception("Unsupported status message: " + status.text)
        statuscode = int(match.group(0))
        if statuscode != 0:
            error_message = root.find('./message')
            raise Exception("Server returned an error. Status: {}, Message \"{}\"".format(statuscode, error_message.text))
        processed_text = root.find('./meta/output')
        if processed_text is None:
            raise Exception("Failed to get output text from server response: \"{}\"".format(processed_text))
        match = re.match("^(\d+) checks processed.$", processed_text.text)
        if match is None:
            raise Exception("Failed to parse count from output text of server response: \"{}\"".format(processed_text.text))
        count = int(match.group(1))
        return count


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('-u', '--url', required=True, help='URL to the NRDP server')
    parser.add_argument('-t', '--token', required=True, help='Authentication token to the NRDP agent')
    parser.add_argument('-H', '--hostname', required=True, help='Hostname of the host/service check')
    parser.add_argument('-s', '--service', help='For service checks, the name of the service associated with the passive check result')
    parser.add_argument('-S', '--state', required=True, help='')
    parser.add_argument('-o', '--output', required=True, help='Text output to submit')
    # parser.add_argument('-d', '--delim', help='')
    parser.add_argument('-c', '--checktype', required=True, help='1 for passive, 0 for passive')

    args = parser.parse_args()
    statuscode = NRDPClient(args.url, args.token).run(args)
    sys.exit(statuscode)
