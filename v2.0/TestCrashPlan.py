# pylint: disable=invalid-name
# pylint: disable=missing-docstring
# pylint: disable=trailing-whitespace
# pylint: disable=trailing-newlines
# pylint: disable=line-too-long
# pylint: disable=too-many-public-methods

import socket
import unittest

from unittest.mock import patch
from Settings import Settings
from RemoteComms import RemoteComms
from MetaData import MetaData
from CrashPlanError import CrashPlanError


class FakeLog(logging.Logger):
    def __init__(self):
        self.val = {'info':[], 'debug':[], 'error':[]}

    def getVal(self,key):
        return "|".join(self.val[key])

    def info(self, val):
        self.val['info'].append(val)

    def debug(self, val):
        self.val['debug'].append(val)

    def error(self, val):
        self.val['error'].append(val)

class FakeRemoteComms(RemoteComms):
    def __init__(self, settings, log):
        # hijacking input
        self.filename = ""
        self.status = settings
        self.message = log
        
    def remoteCommand(self, cmd):
        return self.status, self.message

    def remoteCopy(self, filename):
        self.filename = filename
        
    def getFilename(self):
        return self.filename
        
    def getBackupList(self):
        return ['one', 'two']
        

class FakeMetaData(MetaData):

    def __init__(self, log, comms, settings, jstr):
        self.meta = {'backup-today':'2019-01-01', 'latest-complete':'2019-01-01-012345'}

    def get(self, key):
        return self.meta[key]
        

class TestCrashPlan(unittest.TestCase):
    """Test CrashPlan"""
    
    def setUp(self):
        self.log = FakeLog()
        jstr = """{ "debug-level": false,
            "exclude-files": ".a,.b",
            "exclude-folders": "c,d",
            "settings-dir": "test_myocp",
            "extra-backup-sources": "1",
            "maximum-used-percent": 90,
            "server-address": "",
            "server-name": "myhost"
        }"""
        with patch.object(socket, 'gethostbyname', return_value='15.0.0.1') as mock_method:
            self.settings = Settings(jstr, self.log)
        #self.settings = FakeCrashPlanSettings("path", self.log)
        self.comms = FakeRemoteComms(self.settings, self.log)
        self.meta = FakeMetaData(self.log, self.comms, self.settings, "")
        self.method = None
        
    def test_constructor(self):
        """"""
        CP = CrashPlan(self.settings, self.meta, self.log, self.comms, self.method, False)

if __name__ == '__main__':

    unittest.main(verbosity=1)
    