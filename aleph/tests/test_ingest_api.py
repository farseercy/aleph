import json
from StringIO import StringIO

from aleph.core import db
from aleph.model import Collection
from aleph.index import flush_index
from aleph.tests.util import TestCase


class IngestApiTestCase(TestCase):

    def setUp(self):
        super(IngestApiTestCase, self).setUp()
        self.rolex = self.create_user(foreign_id='user_3')
        self.col = Collection()
        self.col.label = 'Test Collection'
        self.col.foreign_id = 'test_coll_entities_api'
        db.session.add(self.col)
        db.session.flush()
        db.session.commit()
        self.url = '/api/2/collections/%s/ingest' % self.col.id
        self.meta = {
            'countries': ['de', 'us'],
            'languages': ['en']
        }

    def test_upload_logged_out(self):
        data = {'meta': json.dumps(self.meta)}
        res = self.client.post(self.url,
                               data=data)
        assert res.status_code == 403, res

    def test_upload_no_meta(self):
        _, headers = self.login(is_admin=True)
        data = {'meta': 'hihi'}
        res = self.client.post(self.url,
                               data=data,
                               headers=headers)
        assert res.status_code == 400, res

    def test_upload_html_doc(self):
        _, headers = self.login(is_admin=True)
        data = {
            'meta': json.dumps(self.meta),
            'foo': (StringIO("this is a futz with a banana"), 'futz.html')
        }
        res = self.client.post(self.url,
                               data=data,
                               headers=headers)
        assert res.status_code == 200, (res, res.data)
        docs = res.json['documents']
        assert len(docs) == 1, docs
        assert docs[0]['file_name'] == 'futz.html', docs
        flush_index()

        res = self.client.get('/api/2/documents',
                              headers=headers)
        assert res.json['total'] == 1, res.json
        res = self.client.get('/api/2/documents/1',
                              headers=headers)
        assert res.json['countries'] == ['de', 'us'], res.json
        res = self.client.get('/api/2/documents/1/file',
                              headers=headers)
        assert 'futz with a banana' in res.data
        assert 'text/html' in res.content_type, res.content_type

    def test_invalid_meta(self):
        _, headers = self.login(is_admin=True)
        meta = {'title': 3, 'file_name': ''}
        data = {
            'meta': json.dumps(meta),
            'foo': (StringIO("this is a futz with a banana"), 'futz.html')
        }
        res = self.client.post(self.url,
                               data=data,
                               headers=headers)
        assert res.status_code == 400, res
