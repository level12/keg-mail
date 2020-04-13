from html import escape as _escape_html
import logging
import smtplib
import socket
import textwrap

from flask_mail import Message
from flask import current_app

import keg_mail.utils as utils

__all__ = [
    'Email',
    'EmailContent',
    'SendEmailError',
    'escape_html',
    'send_email',
]


log = logging.getLogger(__name__)


def escape_html(content):
    """Takes any string and converts it to an `EmailContent` object where the HTML variant has
    been escaped."""
    return EmailContent(html=_escape_html(content), text=content)


def send_email(recipient, email):
    """Sends an `Email` to a recipient.

    :param recipient: is an email address.
    :param email: is an `Email` object.

    :raises: `SendEmailError`.
    """

    mail_engine = current_app.extensions.get('mail', None)

    if not mail_engine:  # pragma: no cover
        raise SendEmailError('No mail engine')

    message = Message(
        email.subject,
        recipients=[recipient],
        html=email.content.html,
        body=email.content.text
    )

    try:
        mail_engine.send(message)
    except (socket.gaierror, socket.error):  # pragma: no cover
        raise SendEmailError('SMTP Connection error')
    except smtplib.SMTPAuthenticationError:  # pragma: no cover
        raise SendEmailError('SMTP Authentication error')

    if current_app.config.get('MAIL_LOG_MESSAGES', False):
        log.info(message)


class SendEmailError(Exception):
    """Failure to send an email."""
    pass


class EmailContent(object):
    """Captures any content designed to go in an email, including both plaintext and HTML variants.

    This class allows both plaintext and HTML variants of email content to be combined into a single
    entity with a common interface.
    """

    def __init__(self, html, text, clean_whitespace=True):
        """Captures both HTML and text variants of the content.
        :param clean_whitespace: if True content will be dedented and stripped of extra whitespace.
        """
        self.html = textwrap.dedent(html).strip() if clean_whitespace else html
        self.text = textwrap.dedent(text).strip() if clean_whitespace else text

    def format(self, *args, **kwargs):
        """Just like str.format but applies the formatting to both the plaintext and HTML variants.

        If any of the format arguments are `EmailContent` objects, then the appropriate variant will
        be extracted and applied to the corresponding variant in the template.
        """
        select_html = lambda item: getattr(item, 'html', item)  # noqa
        select_text = lambda item: getattr(item, 'text', item)  # noqa
        return EmailContent(
            html=self.html.format(*map(select_html, args), **utils.dict_map(select_html, kwargs)),
            text=self.text.format(*map(select_text, args), **utils.dict_map(select_text, kwargs))
        )

    def join(self, contents):
        """Intercalates this email content between an iterable of other email contents."""
        eval_contents = list(contents)
        return EmailContent(
            html=self.html.join(x.html for x in eval_contents),
            text=self.text.join(x.text for x in eval_contents)
        )

    def __eq__(self, other):
        try:
            return self.html == other.html and self.text == other.text
        except AttributeError:  # pragma: no cover
            return False

    def __hash__(self):
        return hash((self.html, self.text))


class Email(object):
    """Captures the full content of an email: subject and body.

    This class is very much like `EmailContent` but additionally includes a subject.
    """

    def __init__(self, subject, content, type_=None):
        """
        :param subject: the email subject as a string. It may be a template.
        :param content: is a string or an `EmailContent` object. It may be a template.
        """
        self.subject = textwrap.dedent(subject).strip()
        self.content = content
        self.type_ = type_

    def format(self, *args, **kwargs):
        select_text = lambda item: getattr(item, 'text', item)  # noqa
        return Email(
            self.subject.format(*map(select_text, args),
                                **utils.dict_map(select_text, kwargs)),
            self.content.format(*args, **kwargs),
            type_=self.type_
        )

    def __eq__(self, other):
        try:
            return (self.subject == other.subject
                    and self.content == other.content
                    and self.type_ == other.type_)
        except AttributeError:  # pragma: no cover
            return False

    def __hash__(self):
        return hash((self.subject, self.content, self.type_))
