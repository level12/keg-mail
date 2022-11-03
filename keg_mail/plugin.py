import json
import logging
import uuid

import flask_mail


__all__ = [
    'KegMail',
]

from werkzeug.utils import import_string

from keg_mail import cli
from keg_mail.model import EmailLogStatus

log = logging.getLogger(__name__)


class _MailMixin(flask_mail._MailMixin):
    def mailgun_send(self, message, mailgun_opts=None):
        return self.mailgun_client.send(message, mailgun_opts)

    def mailgun_sync_webhooks(self):
        return self.mailgun_client.sync_webhooks(self.mailgun_webhooks)

    def mailgun_clear_webhooks(self):
        return self.mailgun_client.clear_webhooks()

    def mailgun_poll_events(self):
        return self.mailgun_client.poll_events()

    def log_message_sent(self, message, mailgun_response=None, message_uuid=None, app=None,
                         _commit=True):
        if not self.enable_logging:
            return

        from keg.db import db

        message_id = mailgun_response.get('id') if mailgun_response else None

        for recipient in message.recipients:
            entry = self.log_entity_cls(
                address=recipient,
                subject=message.subject,
                status=EmailLogStatus.sent,
                message_id=message_id,
                message_uuid=message_uuid,
            )
            db.session.add(entry)
        db.session.commit()

    def mailgun_update_message_status(self, event_data):
        if not self.enable_logging:
            return
        self.mailgun_client.update_message_status(event_data)

    def send(self, message):
        if self.mailgun_client:
            return self.mailgun_send(message)

        if message.extra_headers is None:
            message.extra_headers = {}
        message.extra_headers['X-Mailgun-Variables'] = json.dumps(
            {'message_uuid': str(uuid.uuid4())}
        )
        return super().send(message)


class _Mail(_MailMixin):
    def __init__(self, server, username, password, port, use_tls, use_ssl,
                 default_sender, debug, max_emails, suppress, mailgun_api_key, mailgun_domain,
                 mailgun_webhooks, enable_logging, log_entity_cls, ascii_attachments=False):
        self.server = server
        self.username = username
        self.password = password
        self.port = port
        self.use_tls = use_tls
        self.use_ssl = use_ssl
        self.default_sender = default_sender
        self.debug = debug
        self.max_emails = max_emails
        self.suppress = suppress
        self.ascii_attachments = ascii_attachments

        self.mailgun_api_key = mailgun_api_key
        self.mailgun_domain = mailgun_domain
        self.mailgun_webhooks = mailgun_webhooks
        self.enable_logging = enable_logging
        self.log_entity_cls = log_entity_cls


class KegMail(flask_mail.Mail):
    def init_mail(self, config, debug=False, testing=False):
        mailgun_domain = config.get('MAIL_MAILGUN_DOMAIN')
        mailgun_api_key = config.get('MAIL_MAILGUN_API_KEY')
        mailgun_test_mode = config.get('MAIL_MAILGUN_TEST_MODE', False)
        enable_logging = config.get('MAIL_ENABLE_LOGGING', False)
        log_entity_loc = config.get('MAIL_LOG_ENTITY')
        log_entity_cls = import_string(log_entity_loc) if log_entity_loc else None
        state = _Mail(
            server=config.get('MAIL_SERVER', '127.0.0.1'),
            username=config.get('MAIL_USERNAME'),
            password=config.get('MAIL_PASSWORD'),
            port=config.get('MAIL_PORT', 25),
            use_tls=config.get('MAIL_USE_TLS', False),
            use_ssl=config.get('MAIL_USE_SSL', False),
            default_sender=config.get('MAIL_DEFAULT_SENDER'),
            debug=int(config.get('MAIL_DEBUG', debug)),
            max_emails=config.get('MAIL_MAX_EMAILS'),
            suppress=config.get('MAIL_SUPPRESS_SEND', testing),
            ascii_attachments=config.get('MAIL_ASCII_ATTACHMENTS', False),
            mailgun_api_key=mailgun_api_key,
            mailgun_domain=mailgun_domain,
            mailgun_webhooks=config.get('MAIL_MAILGUN_WEBHOOKS', {}),
            enable_logging=enable_logging,
            log_entity_cls=log_entity_cls,
        )

        if enable_logging and not log_entity_cls:
            raise ValueError('When mail logging is enabled you must specify a logging entity class')

        if enable_logging:
            flask_mail.email_dispatched.connect(state.log_message_sent)

        state.mailgun_client = None
        if mailgun_domain and mailgun_api_key:
            from keg_mail import mailgun
            state.mailgun_client = mailgun.MailgunClient(
                mailgun_domain,
                mailgun_api_key,
                mailgun_test_mode,
                log_entity_cls=log_entity_cls
            )

        return state

    def init_app(self, app):
        state = super().init_app(app)
        self.init_cli(app, cli_group_name=app.config.get('MAIL_CLI_GROUP_NAME', 'mail'))
        return state

    def init_cli(self, app, cli_group_name='mail'):
        cli.add_cli_to_app(app, cli_group_name=cli_group_name)

    def send(self, message):
        # Flask Mail's inheritance pattern for this class is weird. No actual instance of this class
        # should exist following initialization. Instead an instance of the _Mail class above gets
        # installed as the extension.
        raise NotImplementedError
