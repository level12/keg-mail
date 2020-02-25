import hashlib
import hmac
from unittest import mock

import arrow
import flask
import flask_webtest
from keg_mail import views


@mock.patch.object(views.WebhookBase, 'process_event')
class TestWebhookBase:
    def test_good_signature(self, m_process):
        ts = str(int(arrow.utcnow().float_timestamp)).encode()
        token = b'b' * 32
        key = b'a' * 36

        body = {
            'signature': {
                'timestamp': ts.decode(),
                'token': token.decode(),
                'signature': hmac.new(key=key, msg=ts + token, digestmod=hashlib.sha256).hexdigest()
            },
            'event-data': {'foo': 'bar'}
        }

        client = flask_webtest.TestApp(flask.current_app)
        resp = client.post_json('/noop-webhook', body)

        assert resp.status_code == 200
        assert resp.text == 'OK'

        m_process.assert_called_once_with({'foo': 'bar'})

    def test_bad_signature(self, m_process):
        ts = str(int(arrow.utcnow().float_timestamp)).encode()
        token = b'b' * 32
        key = b'a' * 35 + b'b'

        body = {
            'signature': {
                'timestamp': ts.decode(),
                'token': token.decode(),
                'signature': hmac.new(key=key, msg=ts + token, digestmod=hashlib.sha256).hexdigest()
            },
            'event-data': {}
        }

        client = flask_webtest.TestApp(flask.current_app)
        resp = client.post_json('/noop-webhook', body, status=403)

        assert resp.status_code == 403
        assert not m_process.called
