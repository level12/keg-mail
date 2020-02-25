import cgi
import io
import sys
import urllib.parse
from datetime import timedelta
from operator import attrgetter
from unittest import mock

import arrow
import flask_mail
import keg_mail
from keg.db import db

from keg_mail.mailgun import MailgunClient

import keg_mail_ta.model.entities as ents


class TestMailgunClient:
    def setup_method(self, _):
        ents.MailLog.delete_cascaded()

    def test_send(self, requests_mock):
        requests_mock.post('https://api.mailgun.net/v3/example.com/messages',
                           json={'response': 'ok'})

        client = MailgunClient(domain='example.com', api_key='foo', testing=False)
        message = flask_mail.Message(
            subject='RE: xyz',
            recipients=['bob@example.com', 'joe@example.com'],
            body='very important message',
            html='<blink>very important message</blink>',
            sender='no-reply@aol.com',
            cc=['tim@example.com'],
            bcc=['al@example.com'],
        )
        resp = client.send(message)

        assert resp == {'response': 'ok'}

        assert requests_mock.call_count == 1

        req = requests_mock.request_history[0]
        body = urllib.parse.parse_qs(req.text)

        assert body['from'] == ['no-reply@aol.com']
        assert body['to'] == ['bob@example.com', 'joe@example.com']
        assert body['cc'] == ['tim@example.com']
        assert body['bcc'] == ['al@example.com']
        assert body['subject'] == ['RE: xyz']
        assert body['text'] == ['very important message']
        assert body['html'] == ['<blink>very important message</blink>']
        assert 'attachment' not in body

    def test_send_attachments(self, requests_mock):
        requests_mock.post('https://api.mailgun.net/v3/example.com/messages',
                           json={'response': 'ok'})

        client = MailgunClient(domain='example.com', api_key='foo', testing=False)
        message = flask_mail.Message(
            subject='RE: xyz',
            recipients=['bob@example.com', 'joe@example.com'],
            body='very important message',
            html='<blink>very important message</blink>',
            sender='no-reply@aol.com',
            cc=['tim@example.com'],
            bcc=['al@example.com'],
            attachments=[
                flask_mail.Attachment(
                    filename='foo.jpg',
                    content_type='image/jpeg',
                    data=b'image data',
                ),
                flask_mail.Attachment(
                    filename='bar.pdf',
                    content_type='application/pdf',
                    data=b'document data',
                ),
            ]
        )
        resp = client.send(message)

        assert resp == {'response': 'ok'}

        assert requests_mock.call_count == 1

        req = requests_mock.request_history[0]

        ctype, pdict = cgi.parse_header(req.headers['Content-Type'])
        pdict['boundary'] = pdict['boundary'].encode()
        pdict['CONTENT-LENGTH'] = str(len(req.body))
        body = cgi.parse_multipart(io.BytesIO(req.body), pdict)

        def t(val):
            # Prior to python 3.7 cgi parse results were bytes
            return val.encode() if sys.version_info[:2] < (3, 7) else val

        assert body['from'] == [t('no-reply@aol.com')]
        assert body['to'] == [t('bob@example.com'), t('joe@example.com')]
        assert body['cc'] == [t('tim@example.com')]
        assert body['bcc'] == [t('al@example.com')]
        assert body['subject'] == [t('RE: xyz')]
        assert body['text'] == [t('very important message')]
        assert body['html'] == [t('<blink>very important message</blink>')]
        assert body['attachment'] == [b'image data', b'document data']

    def test_sync_webhooks(self, requests_mock):
        requests_mock.get('https://api.mailgun.net/v3/domains/example.com/webhooks', json={
            "webhooks": {
                "delivered": {
                    "urls": [
                        "https://example.com/delivered_hook1",
                        "https://example.com/delivered_hook2"
                    ]
                },
                "permanent_fail": {
                    "urls": ["https://example.com/perm_fail_hook"]
                },
                "opened": {
                    "urls": ["https://example.com/opened_hook"]
                }
            }
        })
        requests_mock.delete('https://api.mailgun.net/v3/domains/example.com/webhooks/delivered',
                             json={'response': 'ok'})
        requests_mock.post('https://api.mailgun.net/v3/domains/example.com/webhooks',
                           json={'response': 'ok'})
        requests_mock.put('https://api.mailgun.net/v3/domains/example.com/webhooks/permanent_fail',
                          json={'response': 'ok'})

        webhook_def = {
            "permanent_fail": [
                "perm_fail_hook1",
                "perm_fail_hook2",
            ],
            "temporary_fail": ["temp_fail_hook"],
            "opened": ["opened_hook"]
        }

        with mock.patch('flask.url_for') as m_url_for:
            m_url_for.side_effect = lambda x, **kwargs: 'https://example.com/{}'.format(x)
            client = MailgunClient(domain='example.com', api_key='foo', testing=False)
            client.sync_webhooks(webhook_def)

        assert requests_mock.call_count == 4

        history = sorted(requests_mock.request_history, key=attrgetter('method'))

        req1 = history[0]
        assert req1.method == 'DELETE'

        req2 = history[1]
        assert req2.method == 'GET'

        req3 = history[2]
        assert req3.method == 'POST'
        req3_body = urllib.parse.parse_qs(req3.text)
        assert req3_body['id'] == ['temporary_fail']
        assert req3_body['url'] == ['https://example.com/temp_fail_hook']

        req4 = history[3]
        assert req4.method == 'PUT'
        req4_body = urllib.parse.parse_qs(req4.text)
        assert req4_body['url'] == [
            'https://example.com/perm_fail_hook1',
            'https://example.com/perm_fail_hook2',
        ]

    def test_clear_webhooks(self, requests_mock):
        requests_mock.get('https://api.mailgun.net/v3/domains/example.com/webhooks', json={
            "webhooks": {
                "delivered": {
                    "urls": [
                        "https://example.com/delivered_hook1",
                        "https://example.com/delivered_hook2"
                    ]
                },
                "permanent_fail": {
                    "urls": ["https://example.com/perm_fail_hook"]
                },
            }
        })
        requests_mock.delete('https://api.mailgun.net/v3/domains/example.com/webhooks/delivered',
                             json={'response': 'ok'})
        requests_mock.delete(
            'https://api.mailgun.net/v3/domains/example.com/webhooks/permanent_fail',
            json={'response': 'ok'}
        )

        client = MailgunClient(domain='example.com', api_key='foo', testing=False)
        client.clear_webhooks()

        assert requests_mock.call_count == 3

        history = sorted(requests_mock.request_history, key=attrgetter('url'))

        assert history[0].method == 'GET'
        assert history[0].url == 'https://api.mailgun.net/v3/domains/example.com/webhooks'

        assert history[1].method == 'DELETE'
        assert history[1].url == 'https://api.mailgun.net/v3/domains/example.com/webhooks/delivered'

        assert history[2].method == 'DELETE'
        assert history[2].url == (
            'https://api.mailgun.net/v3/domains/example.com/webhooks/permanent_fail'
        )

    def test_poll_events(self, requests_mock):
        now = arrow.utcnow().float_timestamp

        log_ent = ents.MailLog.testing_create(
            status=keg_mail.EmailLogStatus.sent,
            status_updated=arrow.utcnow().shift(hours=-2)
        )

        requests_mock.get('https://api.mailgun.net/v3/example.com/events', json={
            "items": [
                {
                    "id": "a" * 22,
                    "timestamp": now - 60 * 60,
                    "event": "failed",
                    "severity": "temporary",
                    "message": {
                        "headers": {
                          "to": "foo@example.com",
                          "message-id": "20130812164300.28108.52546@samples.mailgun.org",
                          "from": "Excited User <me@samples.mailgun.org>",
                          "subject": "Hello"
                        },
                        "attachments": [],
                        "recipients": [
                            "foo@example.com",
                            "baz@example.com",
                            "bar@example.com"
                        ],
                        "size": 80
                    },
                    "recipient": "baz@example.com",
                    "method": "http"
                }
            ],
            'paging': {
                'next': 'https://api.mailgun.net/v3/example.com/events/page2'
            }
        })

        requests_mock.get('https://api.mailgun.net/v3/example.com/events/page2', json={
            "items": [
                {
                    "id": "b" * 22,
                    "timestamp": now - 25 * 60,
                    "event": "accepted",
                    "message": {
                        "headers": {
                            "to": "foo@example.com",
                            "message-id": "20130812164300.28108.52546@samples.mailgun.org",
                            "from": "Excited User <me@samples.mailgun.org>",
                            "subject": "Hello"
                        },
                        "attachments": [],
                        "recipients": [
                            "foo@example.com",
                            "baz@example.com",
                            "bar@example.com"
                        ],
                        "size": 81
                    },
                    "recipient": "baz@example.com",
                    "method": "http"
                }
            ],
        })

        client = MailgunClient(
            domain='example.com', api_key='foo', testing=False,
            log_entity_cls=ents.MailLog
        )
        with mock.patch.object(client, 'update_message_status') as m_status:
            client.poll_events()

        history = requests_mock.request_history
        assert len(history) == 2

        assert history[0].path == '/v3/example.com/events'
        assert history[0].qs['ascending'] == ['yes']
        assert history[0].qs['begin'] == [str(log_ent.status_updated.float_timestamp)]
        assert arrow.get(float(history[0].qs['end'][0])).is_between(
            arrow.utcnow().shift(minutes=-1),
            arrow.utcnow()
        )
        assert history[0].qs['limit'] == ['300']

        assert history[1].url == 'https://api.mailgun.net/v3/example.com/events/page2'

        m_status.assert_called_once()
        args, kwargs = m_status.call_args
        assert len(args) == 1
        assert args[0]['id'] == 'a' * 22
        assert kwargs == {'_commit': False}

        # Both pages trustworthy
        with mock.patch.object(client, 'update_message_status') as m_status:
            client.poll_events(threshold=timedelta(minutes=10))

        assert m_status.call_count == 2
        assert len(history) == 4
        assert history[2].path == '/v3/example.com/events'
        assert history[3].url == 'https://api.mailgun.net/v3/example.com/events/page2'

        # Neither page is trustworthy
        with mock.patch.object(client, 'update_message_status') as m_status:
            client.poll_events(threshold=timedelta(minutes=120))

        assert m_status.call_count == 0
        assert len(history) == 5
        assert history[4].path == '/v3/example.com/events'

    def test_update_message_status(self, requests_mock):
        now = arrow.utcnow()
        log_ent = ents.MailLog.testing_create(
            status=keg_mail.EmailLogStatus.sent,
            status_updated=now.shift(hours=-2),
            message_id='foo',
            address='baz@example.com'
        )

        event_data = {
            "id": "a" * 22,
            "timestamp": now.float_timestamp,
            "event": "failed",
            "severity": "temporary",
            "message": {
                "headers": {
                    "to": "foo@example.com",
                    "message-id": "foo",
                    "from": "Excited User <me@samples.mailgun.org>",
                    "subject": "Hello"
                },
                "attachments": [],
                "recipients": [
                    "foo@example.com",
                    "baz@example.com",
                    "bar@example.com"
                ],
                "size": 80
            },
            'delivery-status': {
                'message': 'Temp Error'
            },
            "recipient": "baz@example.com",
            "method": "http"
        }

        client = MailgunClient(
            domain='example.com', api_key='foo', testing=False,
            log_entity_cls=ents.MailLog
        )
        client.update_message_status(event_data)
        db.session.expire(log_ent)
        assert log_ent.status == keg_mail.EmailLogStatus.failed_temporary
        assert log_ent.status_updated == now

        # event timestamp is older than current status
        event_data['timestamp'] = now.shift(seconds=-1).float_timestamp
        event_data['severity'] = 'permanent'
        client.update_message_status(event_data)
        db.session.expire(log_ent)
        assert log_ent.status == keg_mail.EmailLogStatus.failed_temporary
        assert log_ent.status_updated == now
        assert log_ent.error_detail == 'Temp Error'

        # ignored event type
        event_data['event'] = 'opened'
        event_data['timestamp'] = log_ent.status_updated.shift(seconds=1).float_timestamp
        del event_data['severity']
        client.update_message_status(event_data)
        db.session.expire(log_ent)
        assert log_ent.status == keg_mail.EmailLogStatus.failed_temporary
        assert log_ent.status_updated == now
        assert log_ent.error_detail == 'Temp Error'

        # record not found
        event_data['event'] = 'delivered'
        event_data['message']['headers']['message-id'] = 'bar'
        event_data['timestamp'] = log_ent.status_updated.shift(seconds=1).float_timestamp
        client.update_message_status(event_data)
        db.session.expire(log_ent)
        assert log_ent.status == keg_mail.EmailLogStatus.failed_temporary
        assert log_ent.status_updated == now
        assert log_ent.error_detail == 'Temp Error'

        # non error status
        event_data['event'] = 'delivered'
        event_data['message']['headers']['message-id'] = 'foo'
        event_data['timestamp'] = log_ent.status_updated.shift(seconds=1).float_timestamp
        client.update_message_status(event_data)
        db.session.expire(log_ent)
        assert log_ent.status == keg_mail.EmailLogStatus.delivered
        assert log_ent.status_updated == now.shift(seconds=1)
        assert log_ent.error_detail is None

        # rejected status
        event_data['event'] = 'rejected'
        event_data['reject'] = {'reason': 'Some Reason'}
        event_data['timestamp'] = log_ent.status_updated.shift(seconds=1).float_timestamp
        client.update_message_status(event_data)
        db.session.expire(log_ent)
        assert log_ent.status == keg_mail.EmailLogStatus.rejected
        assert log_ent.status_updated == now.shift(seconds=2)
        assert log_ent.error_detail == 'Some Reason'
