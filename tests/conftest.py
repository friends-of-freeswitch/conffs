# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
import os
import sys
import shutil
import socket
import pytest
import logging
import logging.config
import conffs


def pytest_addoption(parser):
    '''Add server options for pointing to the engine we will use for testing
    '''
    parser.addoption("--fshost", action="store", dest='fshost',
                     default=None,
                     help="FreeSWITCH server's hostname")
    parser.addoption("--keyfile", action="store", dest='keyfile',
                     default=None,
                     help="Path to ssh private key")
    parser.addoption("--loglevel", action="store", dest='loglevel',
                     default='INFO',
                     help="Global log level to use during testing.")
    parser.addoption("--use-docker", action="store_true", dest='usedocker',
                     help="Toggle use of docker containers for testing")
    parser.addoption("--num-containers", action="store", dest='ncntrs',
                     default=1, help="Number of docker containers to spawn")


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
def confdir():
    """Configure and return the configuration directory
    """
    dirname = os.path.dirname
    dirpath = os.path.abspath(
        os.path.join(
            dirname(dirname(os.path.realpath(__file__))),
            'configs/ci-minimal/'
        )
    )

    # ensure the "original" freeswitch.xml template is used
    orig = os.path.join(dirpath, 'freeswitch.xml.orig')
    shutil.copy(orig, os.path.join(dirpath, 'freeswitch.xml'))
    yield dirpath
    shutil.copy(orig, os.path.join(dirpath, 'freeswitch.xml'))


@pytest.fixture(scope='session')
def containers(request, confdir):
    """Return a sequence of docker containers.
    """
    if request.config.option.usedocker:
        docker = request.getfixturevalue('dockerctl')
        with docker.run(
            'safarov/freeswitch',
            volumes={confdir: {'bind': '/etc/freeswitch/'}},
            num=request.config.option.ncntrs
        ) as containers:
            yield containers
    else:
        pytest.skip(
            "You must specify `--use-docker` to activate containers"
        )


@pytest.fixture(scope='session')
def fshosts(request):
    '''Return the FS test server hostnames passed via the
    ``--fshost`` cmd line arg.
    '''
    argstring = request.config.option.fshost
    addrs = []

    if argstring:
        # construct a list if passed as arg
        fshosts = argstring.split(',')
        yield fshosts

    elif request.config.option.usedocker:
        containers = request.getfixturevalue('containers')
        for container in containers:
            addrs.append(container.attrs['NetworkSettings']['IPAddress'])
        yield addrs

    else:
        pytest.skip("the '--fshost' or '--use-docker` options are required "
                    "to determine the FreeSWITCH server(s) to connect "
                    "to for testing")


@pytest.fixture(scope='session')
def fshost(fshosts):
    """First hostname specified in the ``--fshost`` cli arg.
    """
    return fshosts[0]


@pytest.fixture(scope='session')
def confmng(request, fshost, confdir):
    """ConfigManager instance loaded for the FreeSWITCH process running at
    ``--fshost``.
    """
    kwargs = {}
    option = request.config.option
    keyfile = option.keyfile
    if option.usedocker:
        mode = 'local'
        kwargs['confdir'] = confdir
        kwargs['docker'] = True
        cntr = request.getfixturevalue('containers')[0]
        kwargs['container_id'] = cntr.attrs['Id']
    else:
        mode = 'ssh'
        kwargs['host'] = fshost
        kwargs['keyfile'] = keyfile
        kwargs['cache_key_pw'] = True

    return conffs.manage(mode, **kwargs)


@pytest.fixture
def sof_prof_template(request):
    """Sofia profile template in Python dict form taken directly
    from the default config's ``external`` profile.
    """
    rectemp = ('${caller_id_number}.${target_domain}'
               '.${strftime(%Y-%m-%d-%H-%M-%S)}.wav')
    return {
        'domains': {
            'all': {'parse': 'false', 'alias': 'true'}
        },
        'settings': {
            'forward-unsolicited-mwi-notify': 'false',
            'rtp-timeout-sec': '300',
            'inbound-codec-prefs': 'OPUS,G722,PCMU,PCMA,GSM',
            'hold-music': 'local_stream://moh',
            'watchdog-enabled': 'no',
            'manage-presence': 'true',
            'auth-all-packets': 'false',
            'rfc2833-pt': '101',
            'tls-verify-depth': '2',
            'ext-rtp-ip': 'auto-nat',
            'outbound-codec-prefs': 'OPUS,G722,PCMU,PCMA,GSM',
            'sip-ip': '$${local_ip_v4}',
            'tls-only': 'false',
            'record-path': '/root/sng_fs_runtime/recordings',
            'nonce-ttl': '60',
            'tls-bind-params': 'transport=tls',
            'force-register-db-domain': '$${local_ip_v4}',
            'rtp-timer-name': 'soft',
            'apply-inbound-acl': 'domains',
            'tls-verify-in-subjects': '',
            'auth-calls': 'true',
            'dialplan': 'XML',
            'tls-passphrase': '',
            'local-network-acl': 'localnet.auto',
            'presence-hosts':  '$${local_ip_v4}',
            'inbound-reg-force-matching-username': 'true',
            'watchdog-step-timeout': '30000',
            'sip-trace': 'no',
            'log-auth-failures': 'false',
            'record-template': rectemp,
            'force-subscription-domain': '$${local_ip_v4}',
            'apply-nat-acl': 'nat.auto',
            'sip-capture': 'no',
            'tls-sip-port': '5061',
            'inbound-late-negotiation': 'true',
            'inbound-codec-negotiation': 'generous',
            'sip-port': '9999',  # probably will work on most setups
            'tls-ciphers': 'ALL:!ADH:!LOW:!EXP:!MD5:@STRENGTH',
            'rtp-ip': '$${local_ip_v4}',
            'inbound-zrtp-passthru': 'true',
            'tls-verify-date': 'true',
            'tls': 'false',
            'watchdog-event-timeout': '30000',
            'tls-version': 'tlsv1,tlsv1.1,tlsv1.2',
            'ext-sip-ip': 'auto-nat',
            'challenge-realm': 'auto_from',
            'rtp-hold-timeout-sec': '1800',
            'presence-privacy': 'false',
            'context': 'public',
            'dtmf-duration': '2000',
            'debug': '0',
            'tls-verify-policy': 'none',
            'force-register-domain': '$${local_ip_v4}',
        },
        'gateways': {
        },
        'aliases': []
    }


@pytest.fixture
def mkprofile(confmng, sof_prof_template):
    """A profile factory with settings taken directly from the default
    config's ``external`` profile template.
    """
    profiles = []

    def profile(name):
        confmng.sofia.config.profiles[name] = sof_prof_template
        confmng.commit()
        prof = confmng.sofia.config.profiles[name]
        profiles.append(prof)
        return prof

    yield profile

    for profile in profiles:
        key = profile.key
        del confmng.sofia.config.profiles[key]
        if key in confmng.sofia.status()['profiles']:
            confmng.sofia.stop(profile.key)

    confmng.commit()


@pytest.fixture
def domain_template(request, confmng):
    """Template for a directory domain in Python dict form based on
    the default config.
    """
    # dialvars = '{^^:sip_invite_domain=${dialed_domain}:
    # presence_id=${dialed_user}@${dialed_domain}}'
    dialstring = '${sofia_contact(*/${dialed_user}@${dialed_domain})}'
    pw = 'doggypants'

    return {
        'params': {'dial-string': dialstring},
        'variables': {
            "record_stereo": "true",
            "default_gateway": "$${default_provider}",
            "default_areacode": "$${default_areacode}",
            "transfer_fallback_extension": "operator",
        },
        'groups': {'default': {'users': {
            'doggy': {
                'params': {
                    'password': pw,
                    'vm-password': pw,
                },
                'variables': {
                    "toll_allow": "domestic,international,local",
                    "accountcode": "1000",
                    "user_context": "default",
                    "effective_caller_id_name": "Extension 1000",
                    "effective_caller_id_number": "1000",
                    "outbound_caller_id_name": "$${outbound_caller_name}",
                    "outbound_caller_id_number": "$${outbound_caller_id}",
                    "callgroup": "techsupport",
                }
            }
        }}},
    }


@pytest.fixture
def domain(fshost, confmng, domain_template):
    """A test domain using a template.
    """
    name = socket.gethostbyname(fshost)
    confmng.directory.config[name] = domain_template
    confmng.commit()
    yield confmng.directory.config[name]
    del confmng.directory.config[name]
    confmng.commit()
