from unittest import mock

import flask_mail

from keg_mail.mailgun import MailgunClient
from keg_mail.plugin import _MailMixin


def mock_patch(*args, **kwargs):
    kwargs.setdefault('autospec', False)
    kwargs.setdefault('spec_set', False)
    return mock.patch(*args, **kwargs)


class TestKegMailMixin:
    def setup_method(self):
        client = MailgunClient(domain="keg.example.com", api_key="foo", testing=True)
        self.plugin = _MailMixin()
        self.plugin.mailgun_client = client
        self.message = flask_mail.Message(
            subject="binford tools",
            recipients=["bob@example.com", "joe@example.com"],
            body="more power",
            html="<blink>more power</blink>",
            sender="no-reply@binford.com",
            cc=["tim@example.com"],
            bcc=["al@example.com"],
        )

    @mock_patch("keg_mail.mailgun.MailgunClient.send")
    def test_mailgun_send_no_options(self, m_send):
        self.plugin.mailgun_send(self.message)
        assert m_send.call_args[0][0] is self.message
        assert not m_send.call_args[0][1]

    @mock_patch("keg_mail.mailgun.MailgunClient.send")
    def test_mailgun_send_with_options(self, m_send):
        mailgun_opt = {'opt1': 'bar'}
        self.plugin.mailgun_send(self.message, mailgun_opts=mailgun_opt)
        assert m_send.call_args[0][0] is self.message
        assert m_send.call_args[0][1] == mailgun_opt

    @mock_patch("keg_mail.plugin._MailMixin.mailgun_send")
    def test_plugin_send_mailgun_client_no_options(self, m_send):
        self.plugin.send(self.message)
        assert m_send.call_args[0][0] is self.message
        assert not m_send.call_args[0][1]

    @mock_patch("keg_mail.plugin._MailMixin.mailgun_send")
    def test_plugin_send_mailgun_client_with_options(self, m_send):
        mailgun_opt = {'opt1': 'bar'}
        self.plugin.send(self.message, mailgun_opts=mailgun_opt)
        assert self.message is m_send.call_args[0][0]
        assert m_send.call_args[0][1] == mailgun_opt

    @mock_patch("keg_mail.plugin._MailMixin.mailgun_send")
    def test_plugin_send_no_mailgun_client(self, m_send):
        self.plugin.mailgun_client = None
        self.plugin.send(self.message)
        assert not m_send.called
