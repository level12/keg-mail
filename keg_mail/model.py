import enum
import typing

import sqlalchemy as sa
from sqlalchemy_utils import (
    EmailType,
    ArrowType,
)


__all__ = [
    'EmailLogStatus',
    'MailLogMixin',
]


class EmailLogStatus(enum.Enum):
    sent = 'Sent'
    rejected = 'Rejected'
    delivered = 'Delivered'
    failed_permanent = 'Failed (Permanent)'
    failed_temporary = 'Failed (Temporary)'

    @classmethod
    def db_name(cls):
        return 'enum_email_logs_status'

    @classmethod
    def from_mailgun_event(cls, event: str, severity: typing.Optional[str]):
        mapping = {
            'accepted': cls.sent,
            'rejected': cls.rejected,
            'delivered': cls.delivered,
            'failed': cls.failed_permanent if severity == 'permanent' else cls.failed_temporary
        }
        return mapping.get(event)

    @classmethod
    def error_statuses(cls):
        return [
            cls.rejected,
            cls.failed_temporary,
            cls.failed_permanent,
        ]

    @property
    def is_error(self):
        return self in self.error_statuses()


class MailLogMixin:
    address = sa.Column(EmailType(), nullable=False)
    subject = sa.Column(sa.Unicode, nullable=False)
    status = sa.Column(sa.Enum(EmailLogStatus, name='enum_email_logs_status'), nullable=False)
    status_updated = sa.Column(ArrowType, nullable=True)
    message_id = sa.Column(sa.Unicode)
    message_uuid = sa.Column(sa.Unicode)
    error_detail = sa.Column(sa.Unicode)

    # __table_args__ = (
    #     sa.UniqueConstraint(address, message_id),
    #     sa.UniqueConstraint(message_uuid)
    # )
