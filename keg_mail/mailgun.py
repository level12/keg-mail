import json
import logging
import uuid
from datetime import timedelta
from typing import (
    Any,
    BinaryIO,
    Callable,
    Dict,
    List,
    Optional,
    Tuple,
    Type,
    Union,
)

import arrow
import flask
import flask_mail
import requests
from blazeutils.helpers import ensure_list
from flask import current_app
from ordered_set import OrderedSet

from keg_mail.model import (
    EmailLogStatus,
    MailLogMixin,
)

log = logging.getLogger(__name__)


class MailgunError(Exception):
    pass


FileData = Union[BinaryIO, bytes]

# Covers the data layouts that requests accepts while allowing multiple files with the same
# multi-part field name
RequestFile = Tuple[
    str,  # field name
    Union[
        FileData,
        # filename, file obj
        Tuple[str, FileData],
        # filename, file obj, content type
        Tuple[str, FileData, str],
        # filename, file obj, content type, custom headers
        Tuple[str, FileData, str, Dict[str, Any]]
    ]
]


class MailgunClient:
    api_root_url = 'https://api.mailgun.net/v3'

    def __init__(self, domain: str, api_key: str, testing: bool,
                 log_entity_cls: Optional[Type[MailLogMixin]] = None):
        self.domain = domain
        self.api_key = api_key
        self.log_entity_cls = log_entity_cls
        self.testing = testing

    def _get_auth(self):
        return requests.auth.HTTPBasicAuth('api', self.api_key)

    def _endpoint_url(self, endpoint: str):
        return '{}/{}/{}'.format(self.api_root_url, self.domain, endpoint.lstrip('/'))

    def _request(self, endpoint: str, method: Callable,
                 body: Optional[Dict] = None,
                 params: Optional[Dict] = None,
                 files: Optional[List[RequestFile]] = None,
                 allowed_status=200):

        url = endpoint if endpoint.startswith('http') else self._endpoint_url(endpoint)
        auth = self._get_auth()

        resp = method(url, data=body, params=params, auth=auth, files=files)
        if resp.status_code != allowed_status:
            raise MailgunError(resp.text)

        try:
            resp_data = resp.json()
        except json.JSONDecodeError as err:
            raise MailgunError(str(err))

        return resp_data

    def _post_request(self, endpoint: str, body: Dict,
                      params: Optional[Dict] = None,
                      files: Optional[List[RequestFile]] = None, allowed_status=200):
        return self._request(endpoint, requests.post, body, params, files, allowed_status)

    def _get_request(self, endpoint: str, query_data: Optional[Dict] = None,
                     allowed_status=200):
        return self._request(endpoint, requests.get, None, query_data,
                             allowed_status=allowed_status)

    def _delete_request(self, endpoint: str, query_data: Optional[Dict] = None,
                        allowed_status=200):
        return self._request(endpoint, requests.delete, None, query_data,
                             allowed_status=allowed_status)

    def _put_request(self, endpoint: str, body: Dict,
                     params: Optional[Dict] = None,
                     files: Optional[List[RequestFile]] = None, allowed_status=200):
        return self._request(endpoint, requests.put, body, params, files, allowed_status)

    def _ensure_unique_recipients(self, to: List[str], cc: List[str], bcc: List[str]):
        # We count on the recipients being unique per message_id so the same address in both the
        # "to" and "cc" fields is a problem.
        to = OrderedSet(to)  # Remove duplicates from "to" addresses
        cc = OrderedSet(cc) - to  # If an address is in "to" it needn't be in "cc"
        bcc = OrderedSet(bcc) - to - cc  # If an address is in "to" or "cc" it needn't be in "bcc"

        return list(to), list(cc), list(bcc)

    def send(self, message: flask_mail.Message):
        to, cc, bcc = self._ensure_unique_recipients(
            ensure_list(message.recipients),
            ensure_list(message.cc),
            ensure_list(message.bcc)
        )
        message_uuid = uuid.uuid4()
        request_body = {
            'from': message.sender,
            'to': to,
            'cc': cc,
            'bcc': bcc,
            'subject': message.subject,
            'text': message.body,
            'html': message.html,
            'v:message_uuid': message_uuid,
            'o:testmode': 'yes' if self.testing else 'no'
        }

        files = None
        if message.attachments:
            files = [
                ('attachment', (attachment.filename, attachment.data, attachment.content_type))
                for attachment in message.attachments
            ]

        resp = self._post_request('messages', request_body, files=files)
        flask_mail.email_dispatched.send(
            message,
            mailgun_response=resp,
            message_uuid=message_uuid,
            app=current_app._get_current_object(),
        )
        return resp

    def poll_events(self, after: Optional[arrow.Arrow] = None,
                    threshold=timedelta(minutes=30)):
        from keg.db import db
        import sqlalchemy as sa

        if not self.log_entity_cls:
            raise ValueError('KegMail must be configured with MAIL_LOG_ENTITY to use this feature')

        if after is None:
            after = db.session.query(
                sa.func.max(self.log_entity_cls.status_updated)
            ).filter(
                self.log_entity_cls.status_updated.isnot(None)
            ).scalar()
            after = after if after else arrow.utcnow().shift(minutes=-30)

        for event in self._iter_events(after, threshold=threshold):
            try:
                self.update_message_status(event, _commit=False)
            except Exception:
                # Make sure we release any locked records
                db.session.rollback()
                raise
        db.session.commit()

    def _iter_events(self, after: arrow.Arrow, threshold=timedelta(minutes=30)):
        # Pages of events newer than 30 minutes ago should not be considered complete and
        # trustworthy according to the API documentation:
        # https://documentation.mailgun.com/en/latest/api-events.html#event-polling

        now = arrow.utcnow()

        json_resp = self._get_request('events', {
            'ascending': 'yes',
            'begin': after.float_timestamp,
            'end': now.float_timestamp,
            'limit': 300  # API defined max
        })

        while True:
            if not json_resp['items']:
                break

            #  check if the page is trustworthy
            newest_ts = arrow.get(json_resp['items'][-1]['timestamp'])
            if newest_ts + threshold > now:
                return

            for event in json_resp['items']:
                yield event

            # Get url for next page of results
            next_url = json_resp['paging'].get('next') if json_resp.get('paging') else None
            if next_url is None:
                break

            # Load the next page
            resp = requests.get(next_url, auth=self._get_auth())
            json_resp = resp.json()
            if resp.status_code != 200:
                raise MailgunError(json_resp)

    def update_message_status(self, event_data, _commit=True):
        from keg.db import db

        if not self.log_entity_cls:
            raise ValueError('KegMail must be configured with MAIL_LOG_ENTITY to use this feature')

        new_status = EmailLogStatus.from_mailgun_event(
            event_data['event'],
            event_data.get('severity')
        )
        if new_status is None:
            return

        recipient = event_data['recipient']
        if event_data.get('user-variables'):
            message_uuid = event_data['user-variables'].get('message_uuid')
            # Lock the record in case it is currently being updated via webhook
            log_entry = self.log_entity_cls.query.filter_by(
                message_uuid=message_uuid,
                address=recipient,
            ).with_for_update().first()
        else:
            message_id = event_data['message']['headers']['message-id']
            # Lock the record in case it is currently being updated via webhook
            log_entry = self.log_entity_cls.query.filter_by(
                address=recipient,
                message_id=message_id
            ).with_for_update().first()

        if log_entry is None:
            if _commit:
                db.session.rollback()  # release row lock
            return

        timestamp = arrow.get(float(event_data['timestamp']))
        if log_entry.status_updated and log_entry.status_updated >= timestamp:
            if _commit:
                db.session.rollback()  # release row lock
            return

        log_entry.status = new_status
        log_entry.status_updated = timestamp
        if new_status == EmailLogStatus.rejected:
            log_entry.error_detail = event_data['reject']['reason']
        elif new_status.is_error:
            log_entry.error_detail = event_data['delivery-status']['message']
        else:
            log_entry.error_detail = None

        if _commit:
            db.session.commit()

    def sync_webhooks(self, webhook_defs: dict):
        def url(path: str = ''):
            return '{}/domains/{}/webhooks/{}'.format(
                self.api_root_url, self.domain, path.lstrip('/')).rstrip('/')

        resp = self._get_request(url())
        installed_hooks = resp['webhooks']

        hooks = {}
        for event, endpoints in webhook_defs.items():
            hooks[event] = []
            for endpoint in endpoints:
                if not isinstance(endpoint, str):
                    endpoint, args = endpoint
                else:
                    args = {}
                hooks[event].append(
                    flask.url_for(endpoint, **args, _external=True, _scheme='https')
                )

        # remove installed hooks that are no longer used
        for event in installed_hooks:
            if event not in webhook_defs:
                log.info('Removing {} hooks'.format(event))
                self._delete_request(url(event))

        # update installed webhooks
        for event, urls in hooks.items():
            if event not in installed_hooks:
                log.info('[Keg Mail] Adding {} hooks: {}'.format(event, urls))
                self._post_request(url(), {'id': event, 'url': urls})
            elif installed_hooks[event]['urls'] != urls:
                log.info('Updating {} hooks: {} -> {}'.format(
                    event, installed_hooks[event]['urls'], urls))
                self._put_request(url(event), {'url': urls})

    def clear_webhooks(self):
        resp = self._get_request('{}/domains/{}/webhooks'.format(self.api_root_url, self.domain))
        installed_hooks = resp['webhooks']

        for event in installed_hooks:
            log.info('Removing {} hooks'.format(event))
            url = '{}/domains/{}/webhooks/{}'.format(self.api_root_url, self.domain, event)
            self._delete_request(url)
