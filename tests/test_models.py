# Copyright 2017 Planet Labs, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import io
import json
from sys import version_info
from pytest import deprecated_call
from planet.api.models import Features
from planet.api.models import Paged
from planet.api.models import Request
from planet.api.models import Response
from mock import MagicMock
# try:
#     from StringIO import StringIO as Buffy
# except ImportError:
#     from io import BytesIO as Buffy


def mock_http_response(json, iter_content=None):
    m = MagicMock(name='http_response')
    m.headers = {}
    m.json.return_value = json
    m.iter_content = iter_content
    return m


def make_page(cnt, start, key, next):
    '''fake paged content'''
    return start + cnt, {
        '_links': {
            '_next': next
        },
        key: [{
            'thingee': start + t
        } for t in range(cnt)]
    }


def make_pages(cnt, num, key):
    '''generator of 'cnt' pages containing 'num' content'''
    start = 0
    for p in range(num):
        next = 'page %d' % (p + 1,) if p + 1 < num else None
        start, page = make_page(cnt, start, key, next)
        yield page


class Thingees(Paged):
    ITEM_KEY = 'thingees'


def thingees(cnt, num, key='thingees', body=Thingees):
    req = Request('url', 'auth')
    dispatcher = MagicMock(name='dispatcher', )

    # make 5 pages with 5 items on each page
    pages = make_pages(5, 5, key=key)
    # initial the paged object with the first page
    paged = body(req, mock_http_response(json=next(pages)), dispatcher)
    # the remaining 4 get used here
    dispatcher._dispatch.side_effect = (
        mock_http_response(json=p) for p in pages
    )
    # mimic dispatcher.response
    dispatcher.response = lambda req: Response(req, dispatcher)
    return paged


def test_body_write():
    req = Request('url', 'auth')
    dispatcher = MagicMock(name='dispatcher', )

    chunks = ((str(i) * 16000).encode('utf-8') for i in range(10))
    paged = Paged(req, mock_http_response(
        json=None,
        iter_content=lambda chunk_size: chunks
    ), dispatcher)
    buf = io.BytesIO()
    paged.write(buf)
    assert len(buf.getvalue()) == 160000


def test_paged_items_iter():
    paged = thingees(5, 5)
    expected = 25
    cnt = 0
    for i in paged.items_iter(None):
        if cnt > expected:
            assert False
        assert i['thingee'] == cnt
        cnt += 1
    assert cnt == expected


def test_paged_iter():
    paged = thingees(5, 5)
    pages = list(paged.iter(2))
    assert 2 == len(pages)
    assert 5 == len(pages[0].get()['thingees'])
    assert 5 == len(pages[1].get()['thingees'])


def test_json_encode():
    paged = thingees(5, 5)
    buf = io.StringIO()
    paged.json_encode(buf, 1)
    assert '{"thingees": [{"thingee": 0}]}' == buf.getvalue()


def test_features():
    features = thingees(5, 5, body=Features, key='features')
    buf = io.StringIO()
    features.json_encode(buf, 13)
    features_json = json.loads(buf.getvalue())
    assert features_json['type'] == 'FeatureCollection'
    assert len(features_json['features']) == 13


def test_response():
    req = Request('url', 'auth')
    dispatcher = MagicMock(name='dispatcher', )
    response = Response(req, dispatcher)
    body = response.wait_for()
    assert(body is None)
    # Response.await is removed in Python 3.7
    # and should raise DeprecationWarning in earlier versions.
    if version_info < (3, 7):
        # Response.await raises InvocationError in Tox with Python >= 3.7,
        # so use getattr() instead.
        func = getattr(response, 'await')
        deprecated_call(func)

