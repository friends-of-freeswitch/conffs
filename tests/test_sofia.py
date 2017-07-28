# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
"""
sofia.conf object-relational mappings tests.
"""
import pytest
import time


@pytest.fixture
def profile(confmng, mkprofile):
    profile = mkprofile('doggy')
    yield profile
    confmng.sofia.stop(profile.key)
    time.sleep(1)


def test_read_sofia_section(confmng):
    """Check that the entire section can be read via object maps without error.
    """
    assert repr(confmng.sofia)


def test_create_sofia_profile(profile, confmng):
    """Ensure we can create a profile from scratch, start and stop it.
    """
    assert profile.key not in confmng.sofia.status()['profiles']
    confmng.sofia.start(profile.key)
    assert profile.key in confmng.sofia.status()['profiles']
    confmng.sofia.stop(profile.key)
    assert profile.key not in confmng.sofia.status()['profiles']


def test_sofia_profile_aliases(profile, confmng):
    name = 'myprofile'
    profile['aliases'].append(name)
    confmng.commit()
    confmng.sofia.start(profile.key)
    assert name in confmng.sofia.status()['aliases']
    time.sleep(0.5)
    confmng.sofia.stop(profile.key)
    profile['aliases'].insert(0, 'yourprofile')
    profile['aliases'].insert(1, '2yourprofile')
    assert ('yourprofile', '2yourprofile', name) == tuple(
            profile['aliases'])
    time.sleep(2)  # attempt to avoid a profile restart race/bug in FS
    confmng.sofia.start(profile.key)
    # FIXME: only the last alias is used? bug?
    assert name in confmng.sofia.status()['aliases']

    # verify removal
    del aliases[0]
    assert 'yourprofile' not in aliases
    for key in tuple(aliases):
        aliases.remove(key)
    assert not aliases


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
    confmng.sofia.start(profile.key)
    gateways = confmng.sofia.status()['gateways']
    assert 'mygateway' in gateways
    gw = gateways['mygateway']
    assert '{}@{}'.format(user, domain) in gw['data']


def test_sofia_append_from(profile, confmng):
    newprof = confmng.sofia.config.profiles.appendfrom(profile.key, 'doggy2')
    try:
        assert newprof.key not in confmng.sofia.status()['profiles']
        newprof['settings']['sip-port'] = '1001'

        # starting non-extant profile should fail
        with pytest.raises(confmng.cli.CLIError):
            confmng.sofia.start(newprof.key)

        # push it and move on
        confmng.commit()
        confmng.sofia.start(newprof.key)
        confmng.sofia.start(profile.key)
        assert newprof.key in confmng.sofia.status()['profiles']
        assert profile.key in confmng.sofia.status()['profiles']

        # stop them both
        confmng.sofia.stop(profile.key)
        confmng.sofia.stop(newprof.key)
        assert newprof.key not in confmng.sofia.status()['profiles']
        assert profile.key not in confmng.sofia.status()['profiles']
    finally:
        confmng.sofia.stop(newprof.key)
        del confmng.sofia.config.profiles[newprof.key]
        confmng.commit()
