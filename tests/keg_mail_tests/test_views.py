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
        now = int(arrow.utcnow().float_timestamp)
        ts = str(now).encode()
        token = b'b' * 32
        key = b'a' * 36

        body = {
            'signature': {
                'timestamp': ts.decode(),
                'token': token.decode(),
                'signature': hmac.new(
                    key=key, msg=ts + token, digestmod=hashlib.sha256
                ).hexdigest(),
            },
            'event-data': {'foo': 'bar', 'timestamp': now},
        }

        client = flask_webtest.TestApp(flask.current_app)
        resp = client.post_json('/noop-webhook', body)

        assert resp.status_code == 200
        assert resp.text == 'OK'

        m_process.assert_called_once_with({'foo': 'bar', 'timestamp': now})

    def test_bad_signature(self, m_process):
        now = int(arrow.utcnow().float_timestamp)
        ts = str(now).encode()
        token = b'b' * 32
        key = b'a' * 35 + b'b'

        body = {
            'signature': {
                'timestamp': ts.decode(),
                'token': token.decode(),
                'signature': hmac.new(
                    key=key, msg=ts + token, digestmod=hashlib.sha256
                ).hexdigest(),
            },
            'event-data': {'timestamp': now},
        }

        client = flask_webtest.TestApp(flask.current_app)
        with mock.patch.object(views.time, 'time', return_value=now):
            resp = client.post_json('/noop-webhook', body, status=403)

        assert resp.status_code == 403
        assert not m_process.called

    def test_stale_signature(self, m_process):
        now = int(arrow.utcnow().float_timestamp)
        ts = str(now - views.WebhookBase.signature_max_age_seconds - 1).encode()
        token = b'b' * 32
        key = b'a' * 36
        body = {
            'signature': {
                'timestamp': ts.decode(),
                'token': token.decode(),
                'signature': hmac.new(
                    key=key, msg=ts + token, digestmod=hashlib.sha256
                ).hexdigest(),
            },
            'event-data': {'timestamp': now},
        }

        client = flask_webtest.TestApp(flask.current_app)
        with mock.patch.object(views.time, 'time', return_value=now):
            resp = client.post_json('/noop-webhook', body, status=403)

        assert resp.status_code == 403
        assert not m_process.called

    def test_future_signature(self, m_process):
        now = int(arrow.utcnow().float_timestamp)
        ts = str(now + views.WebhookBase.timestamp_future_tolerance_seconds + 1).encode()
        token = b'b' * 32
        key = b'a' * 36
        body = {
            'signature': {
                'timestamp': ts.decode(),
                'token': token.decode(),
                'signature': hmac.new(
                    key=key, msg=ts + token, digestmod=hashlib.sha256
                ).hexdigest(),
            },
            'event-data': {'timestamp': now},
        }

        client = flask_webtest.TestApp(flask.current_app)
        with mock.patch.object(views.time, 'time', return_value=now):
            resp = client.post_json('/noop-webhook', body, status=403)

        assert resp.status_code == 403
        assert not m_process.called

    def test_event_timestamp_cannot_borrow_future_signature_skew(self, m_process):
        now = int(arrow.utcnow().float_timestamp)
        signature_timestamp = now + views.WebhookBase.timestamp_future_tolerance_seconds
        ts = str(signature_timestamp).encode()
        token = b'b' * 32
        key = b'a' * 36
        body = {
            'signature': {
                'timestamp': ts.decode(),
                'token': token.decode(),
                'signature': hmac.new(
                    key=key, msg=ts + token, digestmod=hashlib.sha256
                ).hexdigest(),
            },
            'event-data': {
                'timestamp': now + views.WebhookBase.timestamp_future_tolerance_seconds + 1
            },
        }

        client = flask_webtest.TestApp(flask.current_app)
        with mock.patch.object(views.time, 'time', return_value=now):
            resp = client.post_json('/noop-webhook', body, status=403)

        assert resp.status_code == 403
        assert not m_process.called

    def test_future_event_timestamp(self, m_process):
        now = int(arrow.utcnow().float_timestamp)
        ts = str(now).encode()
        token = b'b' * 32
        key = b'a' * 36
        body = {
            'signature': {
                'timestamp': ts.decode(),
                'token': token.decode(),
                'signature': hmac.new(
                    key=key, msg=ts + token, digestmod=hashlib.sha256
                ).hexdigest(),
            },
            'event-data': {
                'timestamp': now + views.WebhookBase.timestamp_future_tolerance_seconds + 1
            },
        }

        client = flask_webtest.TestApp(flask.current_app)
        with mock.patch.object(views.time, 'time', return_value=now):
            resp = client.post_json('/noop-webhook', body, status=403)

        assert resp.status_code == 403
        assert not m_process.called

    def test_old_event_with_fresh_signature(self, m_process):
        now = int(arrow.utcnow().float_timestamp)
        ts = str(now).encode()
        token = b'b' * 32
        key = b'a' * 36
        event_data = {'timestamp': now - 24 * 60 * 60}
        body = {
            'signature': {
                'timestamp': ts.decode(),
                'token': token.decode(),
                'signature': hmac.new(
                    key=key, msg=ts + token, digestmod=hashlib.sha256
                ).hexdigest(),
            },
            'event-data': event_data,
        }

        client = flask_webtest.TestApp(flask.current_app)
        resp = client.post_json('/noop-webhook', body)

        assert resp.status_code == 200
        m_process.assert_called_once_with(event_data)

    def test_missing_signing_key(self, m_process):
        client = flask_webtest.TestApp(flask.current_app)

        with mock.patch.dict(flask.current_app.config):
            flask.current_app.config.pop('MAIL_MAILGUN_WEBHOOK_KEY')
            resp = client.post_json('/noop-webhook', {}, status=403)

        assert resp.status_code == 403
        assert not m_process.called

    def test_blank_signing_key(self, m_process):
        now = int(arrow.utcnow().float_timestamp)
        ts = str(now).encode()
        token = b'b' * 32
        body = {
            'signature': {
                'timestamp': ts.decode(),
                'token': token.decode(),
                'signature': hmac.new(
                    key=b'', msg=ts + token, digestmod=hashlib.sha256
                ).hexdigest(),
            },
            'event-data': {'timestamp': now},
        }
        client = flask_webtest.TestApp(flask.current_app)

        for signing_key in ('', '   '):
            with mock.patch.dict(
                flask.current_app.config,
                {'MAIL_MAILGUN_WEBHOOK_KEY': signing_key},
            ):
                resp = client.post_json('/noop-webhook', body, status=403)
            assert resp.status_code == 403

        assert not m_process.called

    def test_malformed_json_body(self, m_process):
        client = flask_webtest.TestApp(flask.current_app)

        resp = client.post(
            '/noop-webhook',
            'not json',
            content_type='application/json',
            status=403,
        )

        assert resp.status_code == 403
        assert not m_process.called

    def test_malformed_webhook_shapes(self, m_process):
        now = str(int(arrow.utcnow().float_timestamp))
        signature = {
            'timestamp': now,
            'token': 'token',
            'signature': 'signature',
        }
        malformed_bodies = (
            None,
            [],
            {},
            {'signature': signature},
            {'signature': None, 'event-data': {'timestamp': now}},
            {'signature': {}, 'event-data': {'timestamp': now}},
            {'signature': signature, 'event-data': None},
            {'signature': signature, 'event-data': []},
        )
        client = flask_webtest.TestApp(flask.current_app)

        for body in malformed_bodies:
            resp = client.post_json('/noop-webhook', body, status=403)
            assert resp.status_code == 403

        assert not m_process.called


@mock.patch('flask.current_app.extensions', autospec=True, spec_set=True)
class TestLogStatusWebhook:
    def test_calls_update_status_method(self, m_extensions):
        now = int(arrow.utcnow().float_timestamp)
        ts = str(now).encode()
        token = b'b' * 32
        key = b'a' * 36

        body = {
            'signature': {
                'timestamp': ts.decode(),
                'token': token.decode(),
                'signature': hmac.new(
                    key=key, msg=ts + token, digestmod=hashlib.sha256
                ).hexdigest(),
            },
            'event-data': {'foo': 'bar', 'timestamp': now},
        }

        client = flask_webtest.TestApp(flask.current_app)
        resp = client.post_json('/log-status-webhook', body)

        assert resp.status_code == 200
        assert resp.text == 'OK'

        m_update = m_extensions.__getitem__.return_value.mailgun_update_message_status
        m_update.assert_called_once_with({'foo': 'bar', 'timestamp': now})
