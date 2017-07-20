#!/usr/bin/env python
#
# Copyright 2016 Sangoma Technologies Inc.
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from setuptools import setup


with open('README.rst') as f:
    readme = f.read()


setup(
    name="conffs",
    version='0.1.0.alpha',
    description='A Python API for configuring FreeSWITCH',
    long_description=readme,
    license='Mozilla',
    author='Sangoma Technologies',
    author_email='qa@eng.sangoma.com',
    maintainer='Tyler Goodlet',
    maintainer_email='tgoodlet@gmail.com',
    url='https://github.com/friends-of-freeswitch/conffs',
    platforms=['linux'],
    packages=[
        'conffs',
    ],
    entry_points={
        'console_scripts': []
    },
    install_requires=[
        'lxml',
        'plumbum',
        'paramiko',
    ],
    tests_require=['pytest'],
    classifiers=[
        'Development Status :: 3 - Alpha',
        'License :: OSI Approved :: Mozilla Public License 2.0 (MPL 2.0)',
        'Operating System :: POSIX :: Linux',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3.5',
        'Intended Audience :: Telecommunications Industry',
        'Intended Audience :: Developers',
        'Topic :: Communications :: Telephony',
        'Environment :: Console',
    ],
)
