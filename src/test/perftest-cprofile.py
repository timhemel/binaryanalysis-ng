import sys
import os
import shutil
import pathlib
import inspect
import unittest
import cProfile

from TestUtil import *

from FileResult import *
from ScanJob import *
# from ScanEnvironment import *

# import bangfilescans

class PerfTestProfile(TestBase):

    def __init__(self,scanfile):
        self.scanfile = scanfile

    def run(self):
        self.setUp()
        self.test_profile_processfile()
        self.tearDown()

    def _make_directory_in_unpackdir(self, dirname):
        try:
            os.makedirs(os.path.join(self.unpackdir, dirname))
        except FileExistsError:
            pass

    def _create_absolute_path_object(self,fn):
        return pathlib.Path(os.path.join(self.unpackdir, fn))

    def test_profile_processfile(self):
        scanpath = pathlib.Path(self.scanfile)
        shutil.copy(scanpath, self.unpackdir / scanpath.name)
        resultsfile = pathlib.Path("profile-%s.stats" % scanpath.name).absolute()
        print(resultsfile)
        fileresult = create_fileresult_for_path(self.unpackdir, pathlib.Path(scanpath.name))
        cProfile.runctx('self.run_scan(fileresult)', globals(), locals(), filename=resultsfile)
        # cProfile.runctx('self.run_scan(fileresult)', globals(), locals())

    def run_scan(self,fileresult):
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




if __name__=="__main__":
    PerfTestProfile(sys.argv[1]).run()

