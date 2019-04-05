# Binary Analysis Next Generation (BANG!)
#
# This file is part of BANG.
#
# BANG is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License, version 3,
# as published by the Free Software Foundation.
#
# BANG is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public
# License, version 3, along with BANG.  If not, see
# <http://www.gnu.org/licenses/>
#
# Copyright 2018-2019 - Armijn Hemel
# Licensed under the terms of the GNU Affero General Public License
# version 3
# SPDX-License-Identifier: AGPL-3.0-only

import hashlib
import tlsh
import string

class FileContentsComputer:
    def __init__(self, read_size):
        self.computers = []
        self.read_size = read_size

    def subscribe(self, input_computer):
        self.computers.append(input_computer)

    def read(self, filename):
        if all(c.supports_memoryview for c in self.computers):
            return self._read_with_memory_view(filename)
        else:
            return self._read_with_file_read(filename)

    def _read_with_file_read(self, filename):
        scanfile = open(filename, 'rb')
        scanfile.seek(0)
        for c in self.computers:
            c.initialize()
        data = scanfile.read(self.read_size)
        while data != b'':
            for c in self.computers:
                c.compute(data)
            data = scanfile.read(self.read_size)
        for c in self.computers:
            c.finalize()
        scanfile.close()

    def _read_with_memory_view(self, filename):
        scanfile = open(filename, 'rb')
        scanfile.seek(0)
        for c in self.computers:
            c.initialize()
        scanbytes = bytearray(self.read_size)
        bytes_read = scanfile.readinto(scanbytes)
        while bytes_read != 0:
            data = memoryview(scanbytes[:bytes_read])
            for c in self.computers:
                c.compute(data)
            bytes_read = scanfile.readinto(scanbytes)
        for c in self.computers:
            c.finalize()
        scanfile.close()


class IsTextComputer:
    supports_memoryview = True
    printable_chars = [ chr(x) in string.printable for x in range(0,256) ]

    def __init__(self):
        self.is_text = True

    def initialize(self):
        pass

    def compute(self, data):
        # this is a little bit faster but echoes an error message to the
        # console, which may slow things down again.
        # try:
        #     return data.tobytes().decode('ascii',errors='strict').isprintable()
        # except UnicodeDecodeError:
        #     return False
        # self.is_text = self.is_text and \
        #     all(chr(x).isprintable() for x in data)
        pc = self.printable_chars
        self.is_text = self.is_text and all(pc[x] for x in data)

    def finalize(self):
        pass

    def get(self):
        return self.is_text


class TLSHComputer:
    supports_memoryview = False

    def __init__(self):
        pass

    def initialize(self):
        self.tlsh_hash = tlsh.Tlsh()

    def compute(self, data):
        self.tlsh_hash.update(data)

    def finalize(self):
        self.tlsh_hash.final()

    def get(self):
        return self.tlsh_hash.hexdigest()


class TLSHComputerMemoryView:
    supports_memoryview = True

    def __init__(self):
        pass

    def initialize(self):
        self.tlsh_hash = tlsh.Tlsh()

    def compute(self, data):
        self.tlsh_hash.update(data.tobytes())

    def finalize(self):
        self.tlsh_hash.final()

    def get(self):
        return self.tlsh_hash.hexdigest()


class ByteCounter:
    supports_memoryview = True

    def __init__(self):
        pass

    def initialize(self):
        self.bytecounter = collections.Counter(
            dict([(i, 0) for i in range(0, 256)]))

    def compute(self, data):
        self.bytecounter.update(data)

    def finalize(self):
        pass

    def get(self):
        return self.bytecounter

hash_algorithms = ['sha256', 'md5', 'sha1']

def _compute_empty_hash_results():
    # global hash_algorithms
    emptyhashes = {}
    results = {}

    # pre-store empty hashes
    for hashtocompute in hash_algorithms:
        emptyhashes[hashtocompute] = hashlib.new(hashtocompute)
        results[hashtocompute] = emptyhashes[hashtocompute].hexdigest()
    return results

emptyhashresults = _compute_empty_hash_results()


class Hasher:
    supports_memoryview = True

    def __init__(self, hash_algorithms):
        self.hash_algorithms = hash_algorithms

    def initialize(self):
        self.hashes = dict([(a, hashlib.new(a))
            for a in self.hash_algorithms])

    def compute(self, data):
        for a in self.hashes:
            self.hashes[a].update(data)

    def finalize(self):
        self.hash_results = dict([(algorithm, computed_hash.hexdigest())
            for algorithm, computed_hash in self.hashes.items()])

    def get(self):
        return self.hash_results
