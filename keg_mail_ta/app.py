from keg.app import Keg

from keg_mail.plugin import KegMail

from keg_mail_ta.views import km_blueprint


class KegMailTestApp(Keg):
    import_name = 'keg_mail_ta'
    db_enabled = True
    use_blueprints = [km_blueprint]
    keyring_enable = False

    def on_init_complete(self):
        self.mail = KegMail(self)
        return self


if __name__ == '__main__':
    from keg_mail_ta import app
    app.KegMailTestApp.cli.main()
