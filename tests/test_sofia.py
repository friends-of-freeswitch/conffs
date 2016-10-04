# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
"""
sofia.conf object-relational mappings tests.
"""
import pytest


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
        'aliases': {
        }
    }


@pytest.fixture
def profile(confmng, sof_prof_template):
    """Deliver a profile with settings taken directly from the default
    config's ``external`` profile template.
    """
    confmng.sofia.profiles['doggy'] = sof_prof_template
    confmng.commit()
    prof = confmng.sofia.profiles['doggy']
    yield prof
    del confmng.sofia.profiles['doggy']
    confmng.commit()
    if 'doggy' in confmng.sofia_status()['profiles']:
        prof.stop(timeout=11)


def test_create_sofia_profile(profile, confmng):
    """Ensure we can create a profile from scratch, start and stop it.
    """
    assert profile.key not in confmng.sofia_status()['profiles']
    profile.start()
    assert profile.key in confmng.sofia_status()['profiles']
    profile.stop(timeout=11)
    assert profile.key not in confmng.sofia_status()['profiles']


def test_sofia_profile_alias(profile, confmng):
    profile['aliases'] = {'name': 'myprofile'}
    confmng.commit()
    profile.start()
    assert 'myprofile' in confmng.sofia_status()['aliases']


def test_sofia_profile_gateway(profile, confmng):
    user = 'doggy'
    domain = 'fakedomain.com'
    profile['gateways'] = {'mygateway': {
        'username': user,
        'password': 'doggypants',
        'realm': domain,
        'from-domain': domain,
        'register': 'false',
        'ping': '30',
    }}
    confmng.commit()
    profile.start()
    gateways = confmng.sofia_status()['gateways']
    assert 'mygateway' in gateways
    gw = gateways['mygateway']
    assert '{}@{}'.format(user, domain) in gw['data']


def test_sofia_append_from(profile, confmng):
    newprof = confmng.sofia.profiles.appendfrom('doggy2', profile.key)
    try:
        assert newprof.key not in confmng.sofia_status()['profiles']
        newprof['settings']['sip-port'] = '1001'

        # starting no-extant profile should fail
        pytest.raises(confmng.fscli.CLIError, newprof.start)

        # push it and move on
        confmng.commit()
        newprof.start()
        profile.start()
        assert newprof.key in confmng.sofia_status()['profiles']
        assert profile.key in confmng.sofia_status()['profiles']

        # stop them both
        profile.stop(timeout=11)
        newprof.stop()
        assert newprof.key not in confmng.sofia_status()['profiles']
        assert profile.key not in confmng.sofia_status()['profiles']
    finally:
        newprof.stop()
        del confmng.sofia.profiles[newprof.key]
        confmng.commit()
