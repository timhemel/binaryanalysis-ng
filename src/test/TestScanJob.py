import sys
import os
import shutil
import pathlib
import inspect
import unittest

import ahocorasick

from TestUtil import *

from FileResult import *
from ScanJob import *
# from ScanEnvironment import *

# import bangfilescans

class TestScanJob(TestBase):

    def _make_directory_in_unpackdir(self, dirname):
        try:
            os.makedirs(os.path.join(self.unpackdir, dirname))
        except FileExistsError:
            pass

    def _create_padding_file_in_directory(self):
        self.parent_dir = pathlib.Path('a')
        self._make_directory_in_unpackdir(self.parent_dir)
        self.padding_file = self.parent_dir / 'PADDING-0x00-0x01'
        f = open(os.path.join(self.unpackdir, self.padding_file), 'wb')
        f.write(b'\0' * 20)
        f.close()

    def _create_absolute_path_object(self,fn):
        return pathlib.Path(os.path.join(self.unpackdir, fn))

    def test_carved_padding_file_has_correct_labels(self):
        self._create_padding_file_in_directory()
        fileresult = create_fileresult_for_path(self.unpackdir, self.padding_file)
        scanjob = ScanJob(fileresult)
        scanjob.set_scanenvironment(self.scan_environment)
        scanjob.initialize()
        unpacker = Unpacker(self.unpackdir)
        scanjob.prepare_for_unpacking()
        scanjob.check_unscannable_file()
        unpacker.append_unpacked_range(0,5) # bytes [0:5) are unpacked
        scanjob.carve_file_data(unpacker)
        j = self.scanfile_queue.get()
        self.assertSetEqual(j.fileresult.labels,set(['padding','synthesized']))

    def test_process_paddingfile_has_correct_labels(self):
        self._create_padding_file_in_directory()
        fileresult = create_fileresult_for_path(self.unpackdir, self.padding_file, labels=set(['padding']))
        scanjob = ScanJob(fileresult)
        self.scanfile_queue.put(scanjob)
        try:
            processfile(self.dbconn, self.dbcursor, self.scan_environment)
        except QueueEmptyError:
            pass
        except ScanJobError as e:
            if e.e.__class__ != QueueEmptyError:
                raise e
        result = self.result_queue.get()
        self.assertSetEqual(result.labels,set(['binary','padding']))

    def test_process_css_file_has_correct_labels(self):
        # /home/tim/bang-test-scrap/bang-scan-jucli3nm/unpack/openwrt-18.06.1-brcm2708-bcm2710-rpi-3-ext4-sysupgrade.img.gz-gzip-1/openwrt-18.06.1-brcm2708-bcm2710-rpi-3-ext4-sysupgrade.img-ext2-1/www/luci-static/bootstrap/cascade.css
        fn = pathlib.Path("a/cascade.css")
        self._copy_file_from_testdata(fn)
        fileresult = create_fileresult_for_path(self.unpackdir,fn,labels=set())
        scanjob = ScanJob(fileresult)
        self.scanfile_queue.put(scanjob)
        try:
            processfile(self.dbconn, self.dbcursor, self.scan_environment)
        except QueueEmptyError:
            pass
        except ScanJobError as e:
            if e.e.__class__ != QueueEmptyError:
                raise e
        result = self.result_queue.get()
        self.assertSetEqual(result.labels,set(['text','css']))

    def test_openwrt_version_has_correct_labels(self):
        # openwrt-18.06.1-brcm2708-bcm2710-rpi-3-ext4-sysupgrade.img.gz-gzip-1/openwrt-18.06.1-brcm2708-bcm2710-rpi-3-ext4-sysupgrade.img-ext2-1/etc/openwrt_version
        fn = pathlib.Path("a/openwrt_version")
        self._copy_file_from_testdata(fn)
        fileresult = create_fileresult_for_path(self.unpackdir,fn,labels=set())
        # fileresult = self._create_fileresult_for_file(fn, os.path.dirname(fn), set())

        scanjob = ScanJob(fileresult)
        self.scanfile_queue.put(scanjob)
        try:
            processfile(self.dbconn, self.dbcursor, self.scan_environment)
        except QueueEmptyError:
            pass
        except ScanJobError as e:
            if e.e.__class__ != QueueEmptyError:
                raise e
        result = self.result_queue.get()
        self.assertSetEqual(result.labels,set(['text']))

    def test_dhcpv6sh_has_correct_labels(self):
        # /home/tim/bang-test-scrap/bang-scan-wd8il1i5/unpack/openwrt-18.06.1-brcm2708-bcm2710-rpi-3-ext4-sysupgrade.img.gz-gzip-1/openwrt-18.06.1-brcm2708-bcm2710-rpi-3-ext4-sysupgrade.img-ext2-1/lib/netifd/proto/dhcpv6.sh
        fn = pathlib.Path("a/dhcpv6.sh")
        self._copy_file_from_testdata(fn)
        fileresult = create_fileresult_for_path(self.unpackdir, fn)

        scanjob = ScanJob(fileresult)
        self.scanfile_queue.put(scanjob)
        try:
            processfile(self.dbconn, self.dbcursor, self.scan_environment)
        except QueueEmptyError:
            pass
        except ScanJobError as e:
            if e.e.__class__ != QueueEmptyError:
                raise e
        result = self.result_queue.get()
        self.assertSetEqual(result.labels,set(['text','script','shell']))

    def test_gzip_unpacks_to_right_directory(self):
        fn = pathlib.Path("a/hello.gz")
        self._copy_file_from_testdata(fn)
        fileresult = create_fileresult_for_path(self.unpackdir, fn, labels=set())

        scanjob = ScanJob(fileresult)
        self.scanfile_queue.put(scanjob)
        try:
            processfile(self.dbconn, self.dbcursor, self.scan_environment)
        except QueueEmptyError:
            pass
        except ScanJobError as e:
            if e.e.__class__ != QueueEmptyError:
                raise e
        result1 = self.result_queue.get()
        result2 = self.result_queue.get()
        self.assertEqual(str(result2.filename), str(fn)+'-gzip-1/hello')

    def test_find_signatures_methods_equivalent(self):
        fn = pathlib.Path("a/hello.gz")
        self._copy_file_from_testdata(fn)
        fn_full = self.unpackdir / fn
        # fn_full = pathlib.Path("/home/tim/bang-testdata/openwrt-18.06.1-brcm2708-bcm2710-rpi-3-ext4-sysupgrade.img.gz")
        filesize = fn_full.stat().st_size

        unpacker = Unpacker(self.unpackdir)
        unpacker.open_scanfile_with_memoryview(fn_full, self.scan_environment.get_maxbytes())
        unpacker.seek_to_last_unpacked_offset()
        unpacker.read_chunk_from_scanfile()

        offsets_no_iter = set()
        offsets_regexps_iter = set()
        offsets_string_iter = set()

        while True:
            os_string_iter = { x
                for s,v in bangsignatures.signatures.items()
                for x in unpacker.find_offsets_for_signature_find_iterator(s, v, filesize)
                }
            os_regexps_iter = { x
                for s,v in bangsignatures.signature_regexps.items()
                for x in unpacker.find_offsets_for_signature_iterator(s, v, filesize)
                }
            os_no_iter = set()
            for s,v in bangsignatures.signatures.items():
                os_no_iter.update(unpacker.find_offsets_for_signature(s, v, filesize))

            offsets_no_iter.update(os_no_iter)
            offsets_regexps_iter.update(os_regexps_iter)
            offsets_string_iter.update(os_string_iter)

            unpacker.file_unpacked({
                'length': 100,
                'filesandlabels': [ (0,[]) ]
                }, filesize)

            unpacker.seek_to_find_next_signature()
            unpacker.read_chunk_from_scanfile()
            if unpacker.get_current_offset_in_file() != filesize:
                break

        unpacker.close_scanfile()

        self.assertSetEqual(set(offsets_regexps_iter), set(offsets_no_iter))
        self.assertSetEqual(set(offsets_string_iter), set(offsets_no_iter))

    def test_string_find_iter_same_as_regexps_iter(self):
        s = "ababacdefghijklmnopqrstuvwxyz"
        o_a1 = re.finditer('aba',s[:10])
        o_b1 = string_find_iter('aba',s, 10)
        la = [ m.start() for m in o_a1 ]
        lb = [ o for o in o_b1 ]
        self.assertListEqual(la, lb)

    def test_re_find_overlapping_iter_same_as_lookahead_regexp_iter(self):
        s = "ababacdefghijklmnopqrstuvwxyz"
        re1 = re.compile('aba')
        re2 = re.compile(r'(?=aba)')
        o_a2 = re.finditer(re2,s)
        o_b1 = re_find_overlapping_iter(re1,s, len(s))
        la = [ m.start() for m in o_a2 ]
        lb = [ pos for pos in o_b1 ]
        self.assertListEqual(la, lb)

    def test_automaton_iter_same_as_re_overlapping_iter(self):
        s = b"ababacdefghijklmnopqrstuvwxyz"
        # res1 = [ re.compile(b'aba'), re.compile(b'de'), re.compile(b'bb') ]
        re1 = re.compile(b'aba')
        automaton = ahocorasick.Automaton()
        automaton.add_word(b'aba', (3, 'first'))
        automaton.make_automaton()

        offsets_re = re_find_overlapping_iter(re1,s, len(s))
        offsets_automaton = ( end_index - signature_length + 1
                for end_index, (signature_length, ftype) in
                    automaton.iter(s, 0, len(s))
            )

        lre = [ pos for pos in offsets_re ]
        laut = [ pos for pos in offsets_automaton ]
        self.assertListEqual(lre, laut)


if __name__=="__main__":
    unittest.main()

