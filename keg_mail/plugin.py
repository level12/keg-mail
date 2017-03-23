import logging
import flask_mail


__all__ = [
    'KegMail',
]

log = logging.getLogger(__name__)


class KegMail(flask_mail.Mail):
    pass
