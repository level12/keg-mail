from blazeutils.strings import randchars


class DefaultProfile:
    SECRET_KEY = randchars()

    # These three just get rid of warnings on the console.
    KEG_KEYRING_ENABLE = False
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    SITE_NAME = 'Keg Mail Demo'
    SITE_ABBR = 'KM Demo'


class TestProfile:
    MAIL_MAILGUN_WEBHOOK_KEY = 'a' * 36
