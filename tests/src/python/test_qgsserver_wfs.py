# -*- coding: utf-8 -*-
"""QGIS Unit tests for QgsServer WFS.

From build dir, run: ctest -R PyQgsServerWFS -V


.. note:: This program is free software; you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation; either version 2 of the License, or
(at your option) any later version.

"""
__author__ = 'René-Luc Dhont'
__date__ = '19/09/2017'
__copyright__ = 'Copyright 2017, The QGIS Project'
# This will get replaced with a git SHA1 when you do a git archive
__revision__ = '$Format:%H$'

import os

# Needed on Qt 5 so that the serialization of XML is consistent among all executions
os.environ['QT_HASH_SEED'] = '1'

import re
import urllib.request
import urllib.parse
import urllib.error

from qgis.server import QgsServerRequest

from qgis.testing import unittest
from qgis.PyQt.QtCore import QSize

import osgeo.gdal  # NOQA

from test_qgsserver import QgsServerTestBase

# Strip path and content length because path may vary
RE_STRIP_UNCHECKABLE = b'MAP=[^"]+|Content-Length: \d+'
RE_ATTRIBUTES = b'[^>\s]+=[^>\s]+'


class TestQgsServerWFS(QgsServerTestBase):

    """QGIS Server WFS Tests"""

    def wfs_request_compare(self, request, version=''):
        project = self.testdata_path + "test_project_wfs.qgs"
        assert os.path.exists(project), "Project file not found: " + project

        query_string = '?MAP=%s&SERVICE=WFS&REQUEST=%s' % (urllib.parse.quote(project), request)
        if version:
            query_string += '&VERSION=%s' % version
        header, body = self._execute_request(query_string)
        self.assert_headers(header, body)
        response = header + body

        reference_name = 'wfs_' + request.lower()
        if version == '1.0.0':
            reference_name += '_1_0_0'
        reference_name += '.txt'

        reference_path = self.testdata_path + reference_name

        self.store_reference(reference_path, response)
        f = open(reference_path, 'rb')
        expected = f.read()
        f.close()
        response = re.sub(RE_STRIP_UNCHECKABLE, b'', response)
        expected = re.sub(RE_STRIP_UNCHECKABLE, b'', expected)

        self.assertXMLEqual(response, expected, msg="request %s failed.\n Query: %s" % (query_string, request))

    def test_project_wfs(self):
        """Test some WFS request"""
        for request in ('GetCapabilities', 'DescribeFeatureType'):
            self.wfs_request_compare(request)
            self.wfs_request_compare(request, '1.0.0')

    def wfs_getfeature_compare(self, requestid, request):
        project = self.testdata_path + "test_project_wfs.qgs"
        assert os.path.exists(project), "Project file not found: " + project

        query_string = '?MAP=%s&SERVICE=WFS&VERSION=1.0.0&REQUEST=%s' % (urllib.parse.quote(project), request)
        header, body = self._execute_request(query_string)

        if requestid == 'hits':
            body = re.sub(b'timeStamp="\d+-\d+-\d+T\d+:\d+:\d+"', b'timeStamp="****-**-**T**:**:**"', body)

        self.result_compare(
            'wfs_getfeature_' + requestid + '.txt',
            "request %s failed.\n Query: %s" % (
                query_string,
                request,
            ),
            header, body
        )

    def test_getfeature(self):
        tests = []
        tests.append(('nobbox', 'GetFeature&TYPENAME=testlayer'))
        tests.append(('startindex2', 'GetFeature&TYPENAME=testlayer&STARTINDEX=2'))
        tests.append(('limit2', 'GetFeature&TYPENAME=testlayer&MAXFEATURES=2'))
        tests.append(('start1_limit1', 'GetFeature&TYPENAME=testlayer&MAXFEATURES=1&STARTINDEX=1'))
        tests.append(('srsname', 'GetFeature&TYPENAME=testlayer&SRSNAME=EPSG:3857'))
        tests.append(('sortby', 'GetFeature&TYPENAME=testlayer&SORTBY=id D'))
        tests.append(('hits', 'GetFeature&TYPENAME=testlayer&RESULTTYPE=hits'))

        for id, req in tests:
            self.wfs_getfeature_compare(id, req)

    def test_wfs_getcapabilities_100_url(self):
        """Check that URL in GetCapabilities response is complete"""
        # empty url in project
        project = os.path.join(self.testdata_path, "test_project_without_urls.qgs")
        qs = "?" + "&".join(["%s=%s" % i for i in list({
            "MAP": urllib.parse.quote(project),
            "SERVICE": "WFS",
            "VERSION": "1.0.0",
            "REQUEST": "GetCapabilities"
        }.items())])

        r, h = self._result(self._execute_request(qs))

        for item in str(r).split("\\n"):
            if "onlineResource" in item:
                self.assertEqual("onlineResource=\"?" in item, True)

        # url well defined in query string
        project = os.path.join(self.testdata_path, "test_project_without_urls.qgs")
        qs = "https://www.qgis-server.org?" + "&".join(["%s=%s" % i for i in list({
            "MAP": urllib.parse.quote(project),
            "SERVICE": "WFS",
            "VERSION": "1.0.0",
            "REQUEST": "GetCapabilities"
        }.items())])

        r, h = self._result(self._execute_request(qs))

        for item in str(r).split("\\n"):
            if "onlineResource" in item:
                self.assertTrue("onlineResource=\"https://www.qgis-server.org?" in item, True)

        # url well defined in project
        project = os.path.join(self.testdata_path, "test_project_with_urls.qgs")
        qs = "?" + "&".join(["%s=%s" % i for i in list({
            "MAP": urllib.parse.quote(project),
            "SERVICE": "WFS",
            "VERSION": "1.0.0",
            "REQUEST": "GetCapabilities"
        }.items())])

        r, h = self._result(self._execute_request(qs))

        for item in str(r).split("\\n"):
            if "onlineResource" in item:
                self.assertEqual("onlineResource=\"my_wfs_advertised_url\"" in item, True)

    def result_compare(self, file_name, error_msg_header, header, body):
        self.assert_headers(header, body)
        response = header + body
        reference_path = self.testdata_path + file_name
        self.store_reference(reference_path, response)
        f = open(reference_path, 'rb')
        expected = f.read()
        f.close()
        response = re.sub(RE_STRIP_UNCHECKABLE, b'', response)
        expected = re.sub(RE_STRIP_UNCHECKABLE, b'', expected)
        self.assertXMLEqual(response, expected, msg="%s\n" % (error_msg_header))

    def wfs_getfeature_post_compare(self, requestid, request):
        project = self.testdata_path + "test_project_wfs.qgs"
        assert os.path.exists(project), "Project file not found: " + project

        query_string = '?MAP={}'.format(urllib.parse.quote(project))
        header, body = self._execute_request(query_string, requestMethod=QgsServerRequest.PostMethod, data=request.encode('utf-8'))

        self.result_compare(
            'wfs_getfeature_{}.txt'.format(requestid),
            "GetFeature in POST for '{}' failed.".format(requestid),
            header, body,
        )

    def test_getfeature_post(self):
        template = """<?xml version="1.0" encoding="UTF-8"?>
<wfs:GetFeature service="WFS" version="1.0.0" {} xmlns:wfs="http://www.opengis.net/wfs" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="http://www.opengis.net/wfs http://schemas.opengis.net/wfs/1.1.0/wfs.xsd">
  <wfs:Query typeName="testlayer" xmlns:feature="http://www.qgis.org/gml">
    <ogc:Filter xmlns:ogc="http://www.opengis.net/ogc">
      <ogc:BBOX>
        <ogc:PropertyName>geometry</ogc:PropertyName>
        <gml:Envelope xmlns:gml="http://www.opengis.net/gml">
          <gml:lowerCorner>8 44</gml:lowerCorner>
          <gml:upperCorner>9 45</gml:upperCorner>
        </gml:Envelope>
      </ogc:BBOX>
    </ogc:Filter>
  </wfs:Query>
</wfs:GetFeature>
"""

        tests = []
        tests.append(('nobbox_post', template.format("")))
        tests.append(('startindex2_post', template.format('startIndex="2"')))
        tests.append(('limit2_post', template.format('maxFeatures="2"')))
        tests.append(('start1_limit1_post', template.format('startIndex="1" maxFeatures="1"')))

        srsTemplate = """<?xml version="1.0" encoding="UTF-8"?>
<wfs:GetFeature service="WFS" version="1.0.0" {} xmlns:wfs="http://www.opengis.net/wfs" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="http://www.opengis.net/wfs http://schemas.opengis.net/wfs/1.1.0/wfs.xsd">
  <wfs:Query typeName="testlayer" srsName="EPSG:3857" xmlns:feature="http://www.qgis.org/gml">
    <ogc:Filter xmlns:ogc="http://www.opengis.net/ogc">
      <ogc:BBOX>
        <ogc:PropertyName>geometry</ogc:PropertyName>
        <gml:Envelope xmlns:gml="http://www.opengis.net/gml">
          <gml:lowerCorner>8 44</gml:lowerCorner>
          <gml:upperCorner>9 45</gml:upperCorner>
        </gml:Envelope>
      </ogc:BBOX>
    </ogc:Filter>
  </wfs:Query>
</wfs:GetFeature>
"""
        tests.append(('srsname_post', srsTemplate.format("")))

        sortTemplate = """<?xml version="1.0" encoding="UTF-8"?>
<wfs:GetFeature service="WFS" version="1.0.0" {} xmlns:wfs="http://www.opengis.net/wfs" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="http://www.opengis.net/wfs http://schemas.opengis.net/wfs/1.1.0/wfs.xsd">
  <wfs:Query typeName="testlayer" xmlns:feature="http://www.qgis.org/gml">
    <ogc:Filter xmlns:ogc="http://www.opengis.net/ogc">
      <ogc:BBOX>
        <ogc:PropertyName>geometry</ogc:PropertyName>
        <gml:Envelope xmlns:gml="http://www.opengis.net/gml">
          <gml:lowerCorner>8 44</gml:lowerCorner>
          <gml:upperCorner>9 45</gml:upperCorner>
        </gml:Envelope>
      </ogc:BBOX>
    </ogc:Filter>
    <ogc:SortBy>
      <ogc:SortProperty>
        <ogc:PropertyName>id</ogc:PropertyName>
        <ogc:SortOrder>DESC</ogc:SortOrder>
      </ogc:SortProperty>
    </ogc:SortBy>
  </wfs:Query>
</wfs:GetFeature>
"""
        tests.append(('sortby_post', sortTemplate.format("")))

        for id, req in tests:
            self.wfs_getfeature_post_compare(id, req)


if __name__ == '__main__':
    unittest.main()
