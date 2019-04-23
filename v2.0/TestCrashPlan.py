# pylint: disable=invalid-name
# pylint: disable=missing-docstring
# pylint: disable=trailing-whitespace
# pylint: disable=trailing-newlines
# pylint: disable=line-too-long
# pylint: disable=too-many-public-methods

import os
import socket
import logging
import unittest

from io import StringIO
from unittest.mock import patch, call
from Settings import Settings
from RemoteComms import RemoteComms
from MetaData import MetaData
from CrashPlan import CrashPlan
from RsyncMethod import BaseMethod
from CrashPlanError import CrashPlanError
from CrashPlan import CrashPlanErrorCodes

class FakeLog(logging.Logger):
    def __init__(self):
        self.val = {'info':[], 'debug':[], 'error':[]}

    def getVal(self, key):
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
        self.settings = settings
        self.message = log
        
    def remoteCommand(self, cmd):
        return self.status, self.message

    def remoteCopy(self, filename):
        self.filename = filename
        
    def getFilename(self):
        return self.filename
        
    def getBackupList(self):
        return ['one', 'two']
        
    def remoteSpace(self):
        return 75

    def removeOldestBackup(self, which):
        pass
        

class FakeMetaData(MetaData):

    def __init__(self, log, comms, settings, jstr):
        self.meta = {'backup-today':'2019-01-01', 'latest-complete':'2019-01-01-012345'}

    def get(self, key):
        return self.meta[key]
        
class FakeMethod(BaseMethod):
    def __init__(self, settings, meta, log, comms):
        super().__init__()

class TestCrashPlan(unittest.TestCase):
    """Test CrashPlan"""
    
    def setUp(self):
        self.log = FakeLog()
        jstr = """{ "debug-level": false,
            "backup-destination": "mydest",
            "exclude-files": ".a,.b",
            "exclude-folders": "c,d",
            "settings-dir": "test_myocp",
            "extra-backup-sources": "/bin",
            "maximum-used-percent": 90,
            "server-address": "",
            "server-name": "myhost"
        }"""
        with patch.object(socket, 'gethostbyname', return_value='15.0.0.1') as mock_method:
            self.settings = Settings(jstr, self.log)
        #self.settings = FakeCrashPlanSettings("path", self.log)
        self.comms = FakeRemoteComms(self.settings, self.log)
        self.meta = FakeMetaData(self.log, self.comms, self.settings, "")
        self.method = FakeMethod(self.settings, self.meta, self.log, self.comms)
        
    def test_constructor(self):
        """"""
        CP = CrashPlan(self.settings, self.meta, self.log, self.comms, self.method, False)

    def test_backupFolder(self):
        """verify backupFolder"""
        CP = CrashPlan(self.settings, self.meta, self.log, self.comms, self.method, False)
        with patch.object(BaseMethod, "run", return_value=CrashPlanErrorCodes.SUCCESS) as mock_run:
            with patch.object(BaseMethod, "buildCommand", return_value=True) as mock_build:
                CP.backupFolder(os.environ['HOME'])
        assert mock_build.called
        local_host = socket.gethostname()
        mock_build.assert_called_with(os.environ['HOME'], f"mydest/{local_host}/WORKING")
        assert mock_run.called

    def test_do_backup(self):
        """verify do_backup"""
        CP = CrashPlan(self.settings, self.meta, self.log, self.comms, self.method, False)
        with patch.object(CrashPlan, "backupFolder", return_value=CrashPlanErrorCodes.SUCCESS) as mock_backup:
            with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
                CP.doBackup()
        assert mock_backup.called
        calls = [call(os.environ['HOME']), call('/bin')]
        mock_backup.assert_has_calls(calls, any_order=False)
        stdout = "Backup successful?  True len(sources) ==  2\nsources:  ['{0!s}', '/bin']\n".format(os.environ['HOME'])
        self.assertEqual(mock_stdout.getvalue(), stdout)

    def test_finishUp(self):
        """verify finishUp"""
        CP = CrashPlan(self.settings, self.meta, self.log, self.comms, self.method, False)
        with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
            CP.backup_successful = True
            CP.finishUp()
        #assert mock_backup.called
        #with patch.object(CrashPlan, "backupFolder", return_value=CrashPlanErrorCodes.SUCCESS) as mock_backup:

    def test_deleteOldestBackup(self):
        """verify deleteOldestBackup"""
        CP = CrashPlan(self.settings, self.meta, self.log, self.comms, self.method, False)
        with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
            CP.deleteOldestBackup()
        

if __name__ == '__main__':

    unittest.main(verbosity=1)
    