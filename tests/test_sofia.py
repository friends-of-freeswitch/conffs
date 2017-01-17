# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
"""
sofia.conf object-relational mappings tests.
"""
import pytest
import time


@pytest.fixture
def profile(mkprofile):
    return mkprofile('doggy')


def test_read_sofia_section(confmng):
    """Check that the entire section can be read via object maps without error.
    """
    assert repr(confmng.sofia)


def test_create_sofia_profile(profile, confmng):
    """Ensure we can create a profile from scratch, start and stop it.
    """
    assert profile.key not in confmng.sofia_status()['profiles']
    profile.start()
    assert profile.key in confmng.sofia_status()['profiles']
    profile.stop()
    assert profile.key not in confmng.sofia_status()['profiles']


def test_sofia_profile_aliases(profile, confmng):
    name = 'myprofile'
    profile['aliases'].append(name)
    confmng.commit()
    profile.start()
    assert name in confmng.sofia_status()['aliases']
    time.sleep(0.5)
    profile.stop()
    profile['aliases'].insert(0, 'yourprofile')
    profile['aliases'].insert(1, '2yourprofile')
    assert ('yourprofile', '2yourprofile', name) == tuple(
            profile['aliases'])
    time.sleep(0.5)
    profile.start()
    # FIXME: only the last alias is used? bug?
    assert name in confmng.sofia_status()['aliases']


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
    newprof = confmng.sofia.profiles.appendfrom(profile.key, 'doggy2')
    try:
        assert newprof.key not in confmng.sofia_status()['profiles']
        newprof['settings']['sip-port'] = '1001'

        # starting non-extant profile should fail
        pytest.raises(confmng.fscli.CLIError, newprof.start)

        # push it and move on
        confmng.commit()
        newprof.start()
        profile.start()
        assert newprof.key in confmng.sofia_status()['profiles']
        assert profile.key in confmng.sofia_status()['profiles']

        # stop them both
        profile.stop()
        newprof.stop()
        assert newprof.key not in confmng.sofia_status()['profiles']
        assert profile.key not in confmng.sofia_status()['profiles']
    finally:
        newprof.stop()
        del confmng.sofia.profiles[newprof.key]
        confmng.commit()
