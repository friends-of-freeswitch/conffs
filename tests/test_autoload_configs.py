# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
"""
Autoload config testing.
"""
import pytest
import time


def test_event_socket(confmng):
    settings = confmng.event_socket['settings']
    pw = settings['password']
    settings['password'] = 'doggy'
    confmng.commit()

    confmng.cli('reload mod_event_socket')
    with pytest.raises(confmng.cli.CLIConnectionError):
        confmng.cli('status')

    # we've locked ourself out by changing the password so get a new cli
    oldcli = confmng.cli._cli
    cli = confmng.cli.get_cli(password='doggy')
    assert cli('status')
    settings['password'] = pw
    confmng.cli._cli = cli
    confmng.commit()
    cli('reload mod_event_socket')

    # verify the old cli command works again
    time.sleep(0.5)
    confmng.cli._cli = oldcli
    assert confmng.cli('status')
