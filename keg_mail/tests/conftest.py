from keg_mail_ta.app import KegMailTestApp


def pytest_configure(config):
    KegMailTestApp.testing_prep()
