# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
"""
Directory configuration section object-relational mappings tests.
"""
import pytest


@pytest.fixture
def domain_template(request, confmng):
    """Template for a directory domain in Python dict form based on
    the default config.
    """
    dialstring = '{^^:sip_invite_domain=${dialed_domain}:presence_id=${dialed_user}@${dialed_domain}}${sofia_contact(*/${dialed_user}@${dialed_domain})}'
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
def domain(confmng, domain_template):
    name = 'test'  # '{}'.format(confmng.cli.eval('$${local_ip_v4}'))
    confmng.directory[name] = domain_template
    confmng.commit()
    yield confmng.directory[name]
    del confmng.directory[name]
    confmng.commit()


def test_push_user(domain, confmng):
    userdata = confmng.get_users()
    users = userdata['test']
    assert len(users) == 1
    assert users[0].userid == 'doggy'


def test_user_count(confmng, domain):
    """Push 300 users, 100 each in a separate group and
    verify they can all be read back using the list_users cmd.
    """
    orig_users = confmng.get_users()

    for igroup in range(3):
        group = domain['groups'].appendfrom(
            'default', 'group_{}'.format(igroup))
        for iuser in range(100):
            group['users'].appendfrom('doggy', 'user_{}'.format(iuser))
        del group['users']['doggy']

    confmng.commit()
    new_users = confmng.get_users()
    assert len(new_users[domain.key]) - len(orig_users[domain.key]) == 300
