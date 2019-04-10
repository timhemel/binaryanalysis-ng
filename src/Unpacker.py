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

import re
import os
import shutil
import stat
import time
import logging

from banglogging import log

import bangunpack
import bangsignatures
from bangsignatures import maxsignaturesoffset

def string_find_iter(needle, haystack, maxsize):
    pos = 0
    l = len(needle)
    while True:
        pos = haystack.find(needle,pos)
        if pos < 0 or pos + l >= maxsize:
            break
        yield pos
        # pos += 1
        pos += l

def re_find_overlapping_iter(pattern, buf, maxsize):
    pos = 0
    while True:
        m = pattern.search(buf[pos:maxsize])
        # print(m, pos,maxsize)
        if m:
            pos += m.start()
            yield pos
            pos += 1
        else:
            break

class Unpacker:
    def __init__(self, unpackroot):
        # Invariant: lastunpackedoffset ==
        # last known position in file with successfully unpacked data
        # everything before this offset is unpacked and identified.
        self.lastunpackedoffset = -1
        self.unpackedrange = []
        self.needsunpacking = True
        # signature based unpacking?
        self.signaturesfound = []
        self.counterspersignature = {}
        self.unpackroot = unpackroot

    def needs_unpacking(self):
        return self.needsunpacking

    def last_unpacked_offset(self):
        return self.lastunpackedoffset

    def unpacked_range(self):
        return self.unpackedrange

    def set_last_unpacked_offset(self, offset):
        self.lastunpackedoffset = offset

    def set_needs_unpacking(self, needsunpacking):
        self.needsunpacking = needsunpacking

    def append_unpacked_range(self, low, high):
        self.unpackedrange.append((low, high))

    def make_data_unpack_directory(self, relpath, filetype, nr=1):
        """makes a data unpack directory.
        relpath is the relative path to the file that is unpacked.
        filetype is the type of the file
        nr is a sequence number that will be increased if the directory
        with that nr already exists.
        returns the sequence number of the directory."""
        while True:
            d = "%s-%s-%d" % (relpath, filetype, nr)
            try:
                os.mkdir(os.path.join(self.unpackroot, d))
                self.dataunpackdirectory = d
                break
            except FileExistsError:
                nr += 1
        return nr

    def remove_data_unpack_directory(self):
        os.rmdir(os.path.join(self.unpackroot,self.dataunpackdirectory))

    def remove_data_unpack_directory_tree(self):
        # Remove the unpacking directory, including any data that
        # might accidentily be there, so first change the
        # permissions of all the files so they can be safely.
        dirwalk = os.walk(os.path.join(self.unpackroot,self.dataunpackdirectory))
        for direntries in dirwalk:
            # make sure all subdirectories and files can
            # be accessed and then removed.
            for subdir in direntries[1]:
                subdirname = os.path.join(direntries[0], subdir)
                if not os.path.islink(subdirname):
                    os.chmod(subdirname,
                             stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)
            for filenameentry in direntries[2]:
                fullfilename = os.path.join(direntries[0], filenameentry)
                if not os.path.islink(fullfilename):
                    os.chmod(fullfilename,
                             stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)
        shutil.rmtree(os.path.join(self.unpackroot,self.dataunpackdirectory))

    def get_data_unpack_directory(self):
        return self.dataunpackdirectory

    def try_unpack_file_for_extension(self, fileresult, scanenvironment, relpath, extension):
        try:
            self.make_data_unpack_directory(relpath, bangsignatures.extensionprettyprint[extension])
            t1 = time.perf_counter_ns()
            r =  bangsignatures.unpack_file_with_extension(fileresult, scanenvironment, extension, self.dataunpackdirectory)
            t2 = time.perf_counter_ns()
            unpacker = bangsignatures.extensiontofunction[extension].__name__
            log(logging.DEBUG, "try_unpack_file_with_extension[%s]: %s = %s" % ( unpacker, r['status'], t2-t1))
            return r
        except AttributeError as ex:
            print(ex)
            self.remove_data_unpack_directory()
            return None

    def open_scanfile(self, filename):
        self.scanfile = open(filename, 'rb')

    def open_scanfile_with_memoryview(self, filename, maxbytes):
        self.scanfile = open(filename, 'rb')
        self.scanbytesarray = bytearray(maxbytes)
        self.scanbytes = memoryview(self.scanbytesarray)

    def seek_to(self, pos):
        self.scanfile.seek(pos)

    def seek_to_last_unpacked_offset(self):
        self.scanfile.seek(max(self.last_unpacked_offset(), 0))

    def get_current_offset_in_file(self):
        return self.scanfile.tell()

    def read_chunk_from_scanfile(self):
        self.offsetinfile = self.get_current_offset_in_file()
        self.bytesread = self.scanfile.readinto(self.scanbytesarray)

    def close_scanfile(self):
        self.scanfile.close()

    def seek_to_find_next_signature(self):
        if self.scanfile.tell() < self.lastunpackedoffset:
            # skip data that has already been unpacked
            self.scanfile.seek(self.lastunpackedoffset)
        else:
            # use an overlap, i.e. go back
            self.scanfile.seek(-maxsignaturesoffset, 1)

    def find_offsets_with_signature_automaton(self, filesize):
        signature_offsets = bangsignatures.signaturesoffset
        prescan_f = bangsignatures.prescan
        res = bangsignatures.signature_automaton.iter(self.scanbytes.tobytes(), 0, self.bytesread)
        for end_index, (signature_length, s) in res:
            offset = end_index - signature_length + 1
            signature_offset = signature_offsets.get(s,0)
            if offset + self.offsetinfile < signature_offset:
                continue
            if not prescan_f(s, self.scanbytes, self.bytesread, filesize, offset, self.offsetinfile):
                continue
            yield (offset + self.offsetinfile - signature_offset, s)

    def find_offsets_for_signature_find_iterator(self, s, v, filesize):
        res = string_find_iter(v, self.scanbytes.obj, self.bytesread)
        for r in res:
            # print("found signature",s,r)
            # print(bytes(self.scanbytes[r:r+len(bangsignatures.signatures[s])]),
            #        bangsignatures.signatures[s])
            if s in bangsignatures.signaturesoffset:
                # skip files that aren't big enough if the
                # signature is not at the start of the data
                # to be carved (example: ISO9660).
                # print("skip?",r, self.offsetinfile,bangsignatures.signaturesoffset[s])
                # print("skip?",r+ self.offsetinfile-bangsignatures.signaturesoffset[s])
                if r + self.offsetinfile - bangsignatures.signaturesoffset[s] < 0:
                    continue

            offset = r
            if not bangsignatures.prescan(s, self.scanbytes, self.bytesread, filesize, offset, self.offsetinfile):
                continue

            # default: store a tuple (offset, signature name)
            if s in bangsignatures.signaturesoffset:
                yield (offset + self.offsetinfile - bangsignatures.signaturesoffset[s], s)
            else:
                yield (offset + self.offsetinfile, s)

    def find_offsets_for_overlapping_signature_iterator(self, s, v, filesize):
        signature_offset = bangsignatures.signaturesoffset.get(s,0)
        prescan_f = bangsignatures.prescan
        res = re_find_overlapping_iter(v, self.scanbytes, self.bytesread)
        for offset in res:
            # skip files that aren't big enough if the
            # signature is not at the start of the data
            # to be carved (example: ISO9660).
            if offset + self.offsetinfile < signature_offset:
                continue

            if not prescan_f(s, self.scanbytes, self.bytesread, filesize, offset, self.offsetinfile):
                continue

            yield (offset + self.offsetinfile - signature_offset, s)


    def find_offsets_for_signature_iterator(self, s, v, filesize):
        signature_offset = bangsignatures.signaturesoffset.get(s,0)
        prescan_f = bangsignatures.prescan
        res = re.finditer(v, self.scanbytes[:self.bytesread])
        # res = re_find_overlapping_iter(v, self.scanbytes, self.bytesread)
        for r in res:
            # skip files that aren't big enough if the
            # signature is not at the start of the data
            # to be carved (example: ISO9660).
            offset = r.start()
            if offset + self.offsetinfile < signature_offset:
                continue

            if not prescan_f(s, self.scanbytes, self.bytesread, filesize, offset, self.offsetinfile):
                continue

            yield (offset + self.offsetinfile - signature_offset, s)

    def find_offsets_for_signature(self, s, v, filesize):
        offsets = set()
        # TODO: precompile regexp patterns in bangsignatures
        res = re.finditer(re.escape(v), self.scanbytes[:self.bytesread])
        if res is not None:
            for r in res:
                if s in bangsignatures.signaturesoffset:
                    # skip files that aren't big enough if the
                    # signature is not at the start of the data
                    # to be carved (example: ISO9660).
                    if r.start() + self.offsetinfile - bangsignatures.signaturesoffset[s] < 0:
                        continue

                offset = r.start()
                if not bangsignatures.prescan(s, self.scanbytes, self.bytesread, filesize, offset, self.offsetinfile):
                    continue

                # default: store a tuple (offset, signature name)
                if s in bangsignatures.signaturesoffset:
                    offsets.add((offset + self.offsetinfile - bangsignatures.signaturesoffset[s], s))
                else:
                    offsets.add((offset + self.offsetinfile, s))
        return offsets

    def offset_overlaps_with_unpacked_data(self, offset):
        return offset < self.lastunpackedoffset

    def try_unpack_file_for_signatures(self, fileresult, scanenvironment, signature, offset):
        try:
            t1 = time.perf_counter_ns()
            r = bangsignatures.signaturetofunction[signature](fileresult, scanenvironment, offset, self.dataunpackdirectory)
            t2 = time.perf_counter_ns()
            unpacker = bangsignatures.signaturetofunction[signature].__name__
            log(logging.DEBUG, "try_unpack_file_for_signatures[%s]: %s = %s" % ( unpacker, r['status'], t2-t1))
            return r
        except AttributeError as ex:
            print(ex)
            self.remove_data_unpack_directory()
            return None

    def try_textonlyfunctions(self, fileresult, scanenvironment, filetype, offset):
        try:
            t1 = time.perf_counter_ns()
            r = bangsignatures.textonlyfunctions[filetype](fileresult, scanenvironment, 0, self.dataunpackdirectory)
            t2 = time.perf_counter_ns()
            unpacker = bangsignatures.textonlyfunctions[filetype].__name__
            log(logging.DEBUG, "try_textonlyfunctions[%s]: %s = %s" % ( unpacker, r['status'], t2-t1))
            return r
        except Exception as e:
            # TODO: make exception more specific, it is too general
            print(e)
            self.remove_data_unpack_directory()
            return None


    def file_unpacked(self, unpackresult, filesize):
        # store the location of where the successfully
        # unpacked file ends (the offset is always 0  here).
        self.lastunpackedoffset = unpackresult['length']

        # store the range of the unpacked data
        self.unpackedrange.append((0, unpackresult['length']))

        # if unpackedfilesandlabels is empty, then no files
        # were unpacked likely because the whole file was the
        # result and didn't contain any files (it was not a
        # container or compresed file)
        if unpackresult['filesandlabels'] == []:
            self.remove_data_unpack_directory()

        # whole file has already been unpacked, so no need for
        # further scanning.
        if unpackresult['length'] == filesize:
            self.needsunpacking = False
