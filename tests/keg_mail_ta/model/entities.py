from keg.db import db
from keg_elements.db.mixins import DefaultColsMixin, MethodsMixin

from keg_mail.model import MailLogMixin


class MailLog(db.Model, DefaultColsMixin, MethodsMixin, MailLogMixin):
    __tablename__ = 'mail_log'
