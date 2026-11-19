from keg.testing import ContextManager
from keg_mail_ta.app import KegMailTestApp
import pytest


def pytest_configure(config):
    KegMailTestApp.testing_prep()


@pytest.fixture(scope='class', autouse=True)
def auto_app_context():
    with ContextManager.get_for(KegMailTestApp).app.app_context():
        yield
