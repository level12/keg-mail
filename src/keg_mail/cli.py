import keg


def add_cli_to_app(app, cli_group_name='mail'):
    mail_ext = app.extensions['mail']

    if mail_ext.mailgun_domain is None or mail_ext.mailgun_api_key is None:
        return

    @app.cli.group(cli_group_name)
    def mail():
        pass

    @mail.command('sync-webhooks')
    def _sync_mailgun_webhooks():
        keg.current_app.extensions['mail'].mailgun_sync_webhooks()

    @mail.command('remove-webhooks')
    def _remove_mailgun_webhooks():
        keg.current_app.extensions['mail'].mailgun_clear_webhooks()

    @mail.command('poll-events')
    def _poll_events():
        keg.current_app.extensions['mail'].mailgun_poll_events()

    mail_ext.cli_group = mail
