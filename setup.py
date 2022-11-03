import os.path as osp
from setuptools import setup, find_packages


cdir = osp.abspath(osp.dirname(__file__))
README = open(osp.join(cdir, 'README.rst')).read()
CHANGELOG = open(osp.join(cdir, 'changelog.rst')).read()

version = {}
with open(osp.join(cdir, 'keg_mail', 'version.py')) as version_fp:
    exec(version_fp.read(), version)

setup(
    name="Keg-Mail",
    description="A mail sending library for keg applications",
    version=version['VERSION'],
    long_description='\n\n'.join((README, CHANGELOG)),
    author="Level 12 Developers",
    author_email="devteam@level12.io",
    url='https://github.com/level12/keg-mail',
    classifiers=[
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
    ],
    license='BSD',
    packages=find_packages(),
    zip_safe=True,
    install_requires=[
        'flask_mail',
        'Keg',
        'SQLAlchemy-Utils',
        'arrow',
    ],
    extras_require={
        'mailgun': [
            'requests',
            'ordered-set',
        ],
        'test': [
            'tox',
            'pytest',
            'pytest-coverage',
            'requests-mock',
            'flask-webtest',
            'KegElements',
        ]
    }
)
