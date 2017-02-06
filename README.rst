sandswitches
============
``sandswitches`` is a Python API for configuring `FreeSWITCH`_ by
modifying its `XML configuration`_.

Client code can for the most part modify the configuration using
standard Python data structures like ``list`` and ``dict``.

Install
-------
::

    pip install git+git://github.com/sangoma/sandswitches.git


API
---
The API is low-level and straightforward; mutating the configuration
is the same as modifying a standard data structure:

.. code-block:: python

    import os
    import sandswitches

    # connect remote; you'll need ssh access and may have to unlock your key
    confmng = sandswitches.manage(
        'megatron', keyfile=os.path.expanduser('~') + '/.ssh/id_rsa')

    confmng.sofia['profiles']['internal']['settings']['sip-port'] = '5069'
    confmng.commit()

    # restart the profile to bind the new port
    confmng.sofia['profiles']['internal'].restart()


If you were to run this in an interactive shell you can get an idea of
the data formatting:

.. code-block:: python

    >>> import pprint
    # convert and pprint as dict
    >>> pprint.pprint(dict(confmng.sofia['profiles']['internal']['settings']))
    {'apply-inbound-acl': 'domains',
    'apply-nat-acl': 'nat.auto',
    'auth-all-packets': 'false',
    'auth-calls': 'true',
    'challenge-realm': 'auto_from',
    'context': 'public',
    'debug': '0',
    'dialplan': 'XML',
    'dtmf-duration': '2000',
    'ext-rtp-ip': 'auto-nat',
    'ext-sip-ip': 'auto-nat',
    'force-register-db-domain': '10.10.8.21',
    'force-register-domain': '10.10.8.21',
    'force-subscription-domain': '10.10.8.21',
    'forward-unsolicited-mwi-notify': 'false',
    'hold-music': 'local_stream://moh',
    'inbound-codec-negotiation': 'generous',
    'inbound-codec-prefs': 'OPUS,G722,PCMU,PCMA,GSM',
    'inbound-late-negotiation': 'true',
    'inbound-reg-force-matching-username': 'true',
    'inbound-zrtp-passthru': 'true',
    'local-network-acl': 'localnet.auto',
    'log-auth-failures': 'false',
    'manage-presence': 'true',
    'nonce-ttl': '60',
    'outbound-codec-prefs':
    'OPUS,G722,PCMU,PCMA,GSM',
    'presence-hosts': '10.10.8.21,10.10.8.21',
    'presence-privacy': 'false',
    'record-path': '/root/sng_fs_runtime/recordings',
    'record-template': '${caller_id_number}.${target_domain}.${strftime(%Y-%m-%d-%H-%M-%S)}.wav',
    'rfc2833-pt': '101',
    'rtp-hold-timeout-sec': '1800',
    'rtp-ip': '10.10.8.21',
    'rtp-timeout-sec': '300',
    'rtp-timer-name': 'soft',
    'sip-capture': 'no',
    'sip-ip': '10.10.8.21',
    'sip-port': '5069',
    'sip-trace': 'no',
    'tls': 'false',
    'tls-bind-params': 'transport=tls',
    'tls-ciphers': 'ALL:!ADH:!LOW:!EXP:!MD5:@STRENGTH',
    'tls-only': 'false',
    'tls-passphrase': '',
    'tls-sip-port': '5061',
    'tls-verify-date': 'true',
    'tls-verify-depth': '2',
    'tls-verify-in-subjects': '',
    'tls-verify-policy': 'none',
    'tls-version': 'tlsv1,tlsv1.1,tlsv1.2',
    'watchdog-enabled': 'no',
    'watchdog-event-timeout': '30000',
    'watchdog-step-timeout': '30000'}

    # object form
    >>> confmng.event_socket
    event_socket({
        'settings': settings({
            'listen-ip': '::', 'password': 'ClueCon', 'listen-port': '8021', 'nat-map': 'false'
         })
    })

    # print the XML contents
    >>> confmng.event_socket.printxml()
    <configuration name="event_socket.conf" description="Socket Client">
      <settings>
        <param name="nat-map" value="false"/>
          <param name="listen-ip" value="::"/>
          <param name="listen-port" value="8021"/>
          <param name="password" value="ClueCon"/>
      </settings>
    </configuration>

.. note::
    There is currently **no** error checking of any sort implemented
    other then what ``fs_cli`` commands like ``reloadxml`` and profile
    starting/stopping return (which is not very much sadly).


Supported config sections
-------------------------
``sandswitches`` uses `object-relational mappings`_
to transform XML *patterns* in the FreeSWITCH config files into simple data
structures. Since each section uses a heterogeneous (read not consistent) set
of patterns, object relations need to be manually specified through a small
schema system;

Patterns need to be mapped explicitly and not all of the XML document has been
fully specced, yet. Currently there is support for the following sections:

- sofia
- directory
- event_socket

The *dialplan* section will probably never be supported as it's far to
complex (and convoluted) to map to a reasonable set of data structures.

Instead we recommend using `switchy`_, another one of our projects
which let's you orchestrate sophisticated call control using FreeSWITCH's
built in event system.


Extending to more sections
**************************
We'd absolutely love to see the entire core config mapped out for use in
``sandswitches``. Currently we've only added what we've needed. If
there's a section missing that you need please feel free to open an issue.

If you want to extend ``sandswitches`` to include your section of choice
take a look at the ``sandswitches.schema`` module and see if
you can figure out how to write your own section *schema*. We'll
hopefully have a better write up on this in the near future.


Caveats
-------
In order to simplify XML processing ``sandswitches`` collapses the
target FreeSWITCH server's XML config to a single master ``freeswitch.xml``.
The original will be backed up with an appropriate time-date suffix which can
renamed back to ``freeswitch.xml`` at any time if you want to revert to
the original multi-file state.


.. links:
.. _FreeSWITCH:
    https://freeswitch.org/
.. _XML configuration:
    https://freeswitch.org/confluence/display/FREESWITCH/Configuring+FreeSWITCH#ConfiguringFreeSWITCH-ConfigurationFiles
.. _switchy:
    https://github.com/sangoma/switchy
.. _object-relational mappings:
    https://en.wikipedia.org/wiki/Object-relational_mapping
