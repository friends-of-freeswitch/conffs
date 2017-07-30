# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
"""
Handy utils.
"""


class RestoreFile(object):
    """Proxy for writing config files and restoring on exit.
    """
    def __init__(self, path, open=open):
        self._cache = None
        self.path = path
        self.open = open

    def _readfile(self, path):
        with self.open('r') as fp:
            return fp.read()

    def _writefile(self, path, contents):
        with self.open('w') as fp:
            fp.write(contents)

    def read(self):
        contents = self._readfile(self.path)

        if self._cache is None:
            self._cache = contents

        return contents

    def write(self, data):
        if self._cache is None:
            self._cache = self._readfile(self.path)

        self._writefile(self.path, data)

    def restore(self):
        if self._cache:
            self._writefile(self.path, self._cache)

    def __enter__(self):
        return self

    def __exit__(self, exception_type, exception_val, trace):
        self.restore()
