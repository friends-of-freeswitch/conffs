# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
import sys
import pytest
import logging
import logging.config
import sandswitches


def pytest_addoption(parser):
    '''Add server options for pointing to the engine we will use for testing
    '''
    parser.addoption("--fshost", action="store", dest='fshost',
                     default='127.0.0.1',
                     help="FreeSWITCH server's hostname")
    parser.addoption("--keyfile", action="store", dest='keyfile',
                     default=None, required=True,
                     help="Path to ssh private key")
    parser.addoption("--loglevel", action="store", dest='loglevel',
                     default='INFO',
                     help="Global log level to use during testing.")


DATEFMT = '%b %d %H:%M:%S'
FORMAT = "%(asctime)s [%(levelname)s] %(name)s %(filename)s:"\
    "%(lineno)d : %(message)s"


@pytest.fixture(scope='session', autouse=True)
def loglevel(request):
    level = request.config.option.loglevel
    isatty = sys.stdout.isatty()
    config = {
        'version': 1,
        'disable_existing_loggers': False,
        'handlers': {
            'stream': {
                'class': 'logging.StreamHandler',
                'formatter': 'colored' if isatty else 'default'
            },
        },
        'formatters': {
            'default': {
                'format': FORMAT,
                'datefmt': DATEFMT
            },
        },
        'loggers': {
            '': {
                'handlers': ['stream'],
                'level': getattr(logging, level.upper()),
                'propagate': True
            },
        }
    }
    try:
        import colorlog
        config['formatters']['colored'] = {
            '()': colorlog.ColoredFormatter,
            'format': "%(log_color)s" + FORMAT,
            'datefmt': DATEFMT,
            'log_colors': {
                'CRITICAL': 'bold_red',
                'ERROR': 'red',
                'WARNING': 'purple',
                'INFO': 'green',
                'DEBUG': 'yellow'
            }
        }
    except ImportError:
        print("colorlog pkg is not installed :(")
    logging.config.dictConfig(config)
    return level


@pytest.fixture(scope='session')
def fshosts(request):
    '''Return the FS test server hostnames passed via the
    `--fshost` cmd line arg.
    '''
    argstring = request.config.option.fshost
    if not argstring:
        pytest.skip("the '--fshost' option is required to determine the "
                    "FreeSWITCH slave server(s) to connect to for testing")
    # construct a list if passed as arg
    fshosts = argstring.split(',')
    return fshosts


@pytest.fixture
def fshost(fshosts):
    """First hostname specified in the ``--fshost`` cli arg.
    """
    return fshosts[0]


@pytest.fixture
def confmng(request, fshost):
    return sandswitches.manage(fshost, keyfile=request.config.option.keyfile)
