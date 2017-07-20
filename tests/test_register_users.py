# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
"""
Integration tests which verify inter-component config and ops.
"""
import time
import socket


def test_reg_to_user(fshost, domain, confmng, mkprofile):
    """Verify that we can register a client to a user on a separate profile
    and make a call between them.
    """
    reg_user = domain['groups']['default']['users']['doggy']
    client = mkprofile('client')
    realm_ip = socket.gethostbyname(fshost)
    client['gateways'] = {
        'doggy': {
            'username': reg_user.key,  # see the domain template
            'password': reg_user['params']['password'],
            'realm': realm_ip,
            'from-domain': realm_ip,
            'register': 'false',  # don't register on startup
            'ping': '30',
        }
    }

    registrar = mkprofile('registrar')
    # use a different port
    registrar['settings']['sip-port'] = str(
        int(client['settings']['sip-port']) - 1)
    registrar['domains']['test'] = {'parse': 'false', 'aliase': 'true'}
    confmng.commit()
    confmng.sofia.start(registrar.key)
    confmng.sofia.start(client.key)

    # register the client gateway to our 'doggy' user
    confmng.sofia.register(client.key, 'doggy')

    # assert the reg was successful
    start = time.time()
    while time.time() - start < 5:
        if confmng.sofia.status()['gateways']['doggy']['state'] == 'REGED':
            break
        time.sleep(0.1)
    else:
        assert confmng.sofia.status()['gateways']['doggy']['state'] == 'REGED'

    # TODO: maybe make a call from the client?

    # teardown
    confmng.sofia.unregister(client.key, 'doggy')
