Keg-Mail
#########

Keg-Mail is a basic wrapper around Flask-Mail which gives some added support for
templates.

It is not finished by any means and in some ways provides little additional
benefit over Flask-Mail.


Usage
=====

.. code::

  $ pip install keg-mail


Initialize Keg-Mail in you application

.. code::

  import flask
  import keg_mail
  from keg.signals import app_ready
  from keg import Keg

  bp = flask.blueprint('main', __name__)
  mail = keg_mail.KegMail()

  class App(Keg):
    use_blueprints = [bp]


Initialize the extension with the application

.. code::

  @app_ready.connect
  def init_extensions(app):
      """Init custom extensions used by this application"""

      mail.init_app(app)


Define email content

.. code::

  import keg_mail

  hello_world_content = keg_mail.EmailContent(
    text='Hello {name}!'
    html='<h1>Hello {name}!</h1>'
  )


Send the email

.. code::

  from app import mail
  import app.emails as emails
  import keg_mail

  bp.route('/')
  def index():
      mail.send(
          'you@something.com'
          keg_mail.Email(
            subject="Hello {name}!",
            content=emails.hello_world_content,
          ).format(name='You")
      )


Test the email

.. code::

  from app import mail

  def test_send_mail():
      with mail.record_messages() as outbox:
          resp = app.test_client.get('/')
          assert len(outbox) == 1
          assert outbox[0].subject == "Hello You!"
          assert outbox[0].body == "Hello You!"
