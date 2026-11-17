# Keg-Mail

[![nox](https://github.com/level12/keg-mail/actions/workflows/nox.yaml/badge.svg)](https://github.com/level12/keg-mail/actions/workflows/nox.yaml)

Keg-Mail is a basic wrapper around Flask-Mail which adds support for email
templates and Mailgun integrations.


## Usage

```shell
pip install keg-mail
```

Initialize Keg-Mail in your application:

```python
import flask
from keg import Keg
from keg.signals import app_ready
import keg_mail

bp = flask.Blueprint('main', __name__)
mail = keg_mail.KegMail()


class App(Keg):
    use_blueprints = [bp]


@app_ready.connect
def init_extensions(app):
    """Initialize custom extensions used by this application."""
    mail.init_app(app)
```

Define email content:

```python
import keg_mail

hello_world_content = keg_mail.EmailContent(
    text='Hello {name}!',
    html='<h1>Hello {name}!</h1>',
)
```

Send the email:

```python
from app import mail
import app.emails as emails
import keg_mail


@bp.route('/')
def index():
    mail.send_email(
        'you@example.com',
        keg_mail.Email(
            subject='Hello {name}!',
            content=emails.hello_world_content,
        ).format(name='You'),
    )
```

Test the email:

```python
from app import mail


def test_send_mail():
    with mail.record_messages() as outbox:
        app.test_client.get('/')
        assert len(outbox) == 1
        assert outbox[0].subject == 'Hello You'
```


## Changelog


### 0.3.1 — 2024-06-21

- Resolve a missed signal signature change.


### 0.3.0 — 2024-06-21

- Automatically pass the reply-to header to Mailgun.
- Support Flask-Mail 0.10.0 signal changes.

Earlier release notes remain available in [changelog.rst](changelog.rst).


## Development


### Copier template

Project structure and tooling mostly derive from
[Coppy](https://github.com/level12/coppy). See its documentation for context and
additional instructions. Update this project by following Coppy's
[template update instructions](https://github.com/level12/coppy/wiki#updating-a-project).


### Project setup

1. Install the [host dependencies](https://github.com/level12/coppy/wiki/Mise).
2. Run `uv sync`.
3. Install the hooks with `prek install`.
4. Run the checks with `nox`.


### Versions

Use `mise run version show` to show the current version and
`mise run version bump` to create a version commit and tag.
