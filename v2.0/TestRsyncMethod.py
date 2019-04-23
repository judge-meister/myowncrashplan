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
import subprocess

from unittest.mock import patch, Mock
from Settings import Settings
from RemoteComms import RemoteComms
from MetaData import MetaData
from RsyncMethod import RsyncMethod
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
        #print(val)

class FakeMetaData(MetaData):
    def __init__(self, log, comms, settings, jstr):
        self.meta = {'backup-today':'2019-01-01', 'latest-complete':'2019-01-01-012345'}
    def get(self, key):
        return self.meta[key]
        
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
        
class FakeStdOut():
    def __init__(self):
        self.count=0
        
    def readline(self):
        if self.count < 3:
            self.count +=1
            return b'abc'
        return b''
        
class FakeProc():
    stdout = FakeStdOut()
    stderr = FakeStdOut()
    #returncode = None

    def poll():
        #returncode = 1
        return 0


class TestRsyncMethod(unittest.TestCase):
    """Test RsyncMethod"""
    
    def setUp(self):
        self.log = FakeLog()
        jstr = """{ "debug-level": false,
            "backup-destination": "mydest",
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

    def tearDown(self):
        if os.path.exists('/Users/judge/test_myocp/myocp_excl'):
            os.unlink('/Users/judge/test_myocp/myocp_excl')
            
    def test_constructor(self):
        rsync = RsyncMethod(self.settings, self.meta, self.log, self.comms, False)

    def test_buildCommand(self):
        """verify buildCommand returns expected string"""
        rsync = RsyncMethod(self.settings, self.meta, self.log, self.comms, False)
        rsync.settings.set("backup-destination", '/tmp')
        rsync.buildCommand("/Users/judge", "/zdata/myowncrashplan/Prometheus.local/WORKING")
        self.assertEqual(rsync.cmd, 'rsync -av --log-file=/Users/judge/.myocp/backup.log --link-dest=../two --bwlimit=2500 --timeout=300 --delete --delete-excluded  --exclude-from=/Users/judge/test_myocp/myocp_excl /Users/judge "15.0.0.1:/zdata/myowncrashplan/Prometheus.local/WORKING" ')

    def test_buildCommand_2(self):
        """verify buildCommand returns expected string"""
        rsync = RsyncMethod(self.settings, self.meta, self.log, self.comms, True)
        rsync.settings.set("backup-destination", '/tmp')
        rsync.buildCommand("/Users/judge", "/zdata/myowncrashplan/Prometheus.local/WORKING")
        self.assertEqual(rsync.cmd, 'rsync -av --log-file=/Users/judge/.myocp/backup.log --dry-run --link-dest=../two --bwlimit=2500 --timeout=300 --delete --delete-excluded  --exclude-from=/Users/judge/test_myocp/myocp_excl /Users/judge "15.0.0.1:/zdata/myowncrashplan/Prometheus.local/WORKING" ')

    def test__create_excl_file_1(self):
        """verify rsync_excl fie is  created."""
        rsync = RsyncMethod(self.settings, self.meta, self.log, self.comms, False)
        rsync.exclude_file = os.path.join(os.environ['HOME'],"temp/myocp_excl")
        rsync._create_exclude_file()
        self.assertTrue(os.path.exists(rsync.exclude_file))
        self.assertEqual(self.log.getVal('info').split('|')[0], 'Settings file loaded.')
        self.assertEqual(self.log.getVal('info').split('|')[1], 'Settings file verified.')
        #self.assertEqual(self.log.getVal('info').split('|')[2], 'rsync exclusions file created at %s/temp/myocp_excl' % os.environ['HOME'])
        with open(rsync.exclude_file, 'r') as fp:
            self.assertEqual(fp.read(), ".a\n.b\nc\nd")
        os.unlink(rsync.exclude_file)

    def test__create_excl_file_2(self):
        """verify creation of rsync_excl file with debug logged."""
        rsync = RsyncMethod(self.settings, self.meta, self.log, self.comms, False)
        rsync.settings.set('debug-level', 1)
        rsync.exclude_file = os.path.join(os.environ['HOME'],"temp/myocp_excl")
        rsync._create_exclude_file()
        self.assertTrue(os.path.exists(rsync.exclude_file))
        self.assertEqual(self.log.getVal('info').split('|')[0], 'Settings file loaded.')
        self.assertEqual(self.log.getVal('info').split('|')[1], 'Settings file verified.')
        #self.assertEqual(self.log.getVal('info').split('|')[2], 'rsync exclusions file created at %s/temp/myocp_excl' % os.environ['HOME'])
        with open(rsync.exclude_file, 'r') as fp:
            self.assertEqual(fp.read(), ".a\n.b\nc\nd")
        os.unlink(rsync.exclude_file)
        self.assertEqual(self.log.getVal('debug').split('|')[0], "_create_exclude_file() - EXCLUDES = \n['.a', '.b', 'c', 'd']")
        self.assertEqual(self.log.getVal('debug').split('|')[1], '_create_exclude_file() - %s/temp/myocp_excl exists True' % os.environ['HOME'])

    @patch('os.unlink')
    def test__remove_exclude_file_1(self, mock_unlink):
        """verify removal of excl file logs an info when the file does not exist"""
        rsync = RsyncMethod(self.settings, self.meta, self.log, self.comms, False)
        rsync._remove_exclude_file()
        self.assertEqual(self.log.getVal('info').split('|')[0], 'Settings file loaded.')
        self.assertEqual(self.log.getVal('info').split('|')[1], 'Settings file verified.')
        self.assertEqual(self.log.getVal('info').split('|')[2], 'rsync exclusions file does not exist.')

    def test__remove_excl_file_2(self):
        """verify that rsync_excl file in correctly removed."""
        rsync = RsyncMethod(self.settings, self.meta, self.log, self.comms, False)
        self.assertEqual(rsync.exclude_file, os.path.join(os.environ['HOME'],"test_myocp","myocp_excl"))
        rsync.exclude_file = os.path.join(os.environ['HOME'],"temp/myocp_excl")
        with open(rsync.exclude_file, 'w') as fp:
            fp.write('{}')
        rsync._remove_exclude_file()
        self.assertFalse(os.path.exists(rsync.exclude_file))
        self.assertEqual(self.log.getVal('info').split('|')[0], 'Settings file loaded.')
        self.assertEqual(self.log.getVal('info').split('|')[1], 'Settings file verified.')
        #self.assertEqual(self.log.getVal('info').split('|')[2], 'rsync exclusions file removed.')

    @patch('subprocess.Popen')
    def test_run(self, mock_subproc_popen):
        """verify run"""
        proc_mock = Mock()
        attrs = {'communicate.return_value': ('output', 'error')}
        proc_mock.configure_mock(**attrs)
        proc_mock.__enter__ = Mock(return_value=FakeProc)
        proc_mock.__exit__ = Mock(return_value=0)
        #proc_mock.returncode
        mock_subproc_popen.returncode.return_value = 'abc'
        mock_subproc_popen.return_value = proc_mock 
        
        rsync = RsyncMethod(self.settings, self.meta, self.log, self.comms, False)
        rsync.settings.set("backup-destination", '/tmp')
        rsync.buildCommand("/Users/judge", "/zdata/myowncrashplan/Prometheus.local/WORKING")
        rsync.run()

        assert mock_subproc_popen.called

    def test__interpret_results(self):
        """verify _interpretResults"""
        rsync = RsyncMethod(self.settings, self.meta, self.log, self.comms, False)
        st, rt = (2, "unknown error")
        result = rsync._interpretResults(st, rt)
        self.assertEqual(result, CrashPlanErrorCodes.UNKNOWN_ERROR)
        self.assertEqual(self.log.getVal('info').split('|')[0], 'Settings file loaded.')
        self.assertEqual(self.log.getVal('info').split('|')[1], 'Settings file verified.')
        self.assertEqual(self.log.getVal('info').split('|')[2], f"do_backup - status = [{st}]")
        self.assertEqual(self.log.getVal('info').split('|')[3], f"rsync returned '{rt}' (code {st})")

        st, rt = (24, "")
        result = rsync._interpretResults(st, rt)
        self.assertEqual(result, CrashPlanErrorCodes.SUCCESS)
        self.assertEqual(self.log.getVal('info').split('|')[4], f"do_backup - status = [{st}]")
        self.assertTrue(self.log.getVal('info').split('|')[5].startswith("Some files vanished (code 24 or 6144)"))
        
        st, rt = (1, "some vanished files")
        result = rsync._interpretResults(st, rt)
        self.assertEqual(result, CrashPlanErrorCodes.UNKNOWN_ERROR)
        self.assertEqual(self.log.getVal('info').split('|')[6], f"do_backup - status = [{st}]")
        self.assertEqual(self.log.getVal('info').split('|')[7], f"rsync returned '{rt}' (code {st})")
        
        st, rt = (6144, "")
        result = rsync._interpretResults(st, rt)
        self.assertEqual(result, CrashPlanErrorCodes.SUCCESS)
        self.assertEqual(self.log.getVal('info').split('|')[8], f"do_backup - status = [{st}]")
        self.assertTrue(self.log.getVal('info').split('|')[9].startswith("Some files vanished (code 24 or 6144)"))
        
        st, rt = (23, "")
        result = rsync._interpretResults(st, rt)
        self.assertEqual(result, CrashPlanErrorCodes.SUCCESS)
        self.assertEqual(self.log.getVal('info').split('|')[10], f"do_backup - status = [{st}]")
        self.assertTrue(self.log.getVal('info').split('|')[11].startswith("Some files could not be transferred (code 23)"))
        
        st, rt = (0, "")
        result = rsync._interpretResults(st, rt)
        self.assertEqual(result, CrashPlanErrorCodes.SUCCESS)
        self.assertEqual(self.log.getVal('info').split('|')[12], f"do_backup - status = [{st}]")
        self.assertEqual(len(self.log.getVal('info').split('|')), 13)
        


"""
def run_script(file_path):
  process = subprocess.Popen(['myscript', -M, file_path], stdout=subprocess.PIPE)
  output,err = process.communicate()
  return process.returncode

@mock.patch('subprocess.Popen')
def test_run_script(self, mock_subproc_popen):
  process_mock = mock.Mock()
  attrs = {'communicate.return_value': ('output', 'error')}
  process_mock.configure_mock(**attrs)
  mock_subproc_popen.return_value = process_mock 
  am.account_manager("path") # this calls run_script somewhere, is that right?
  self.assertTrue(mock_subproc_popen.called)
"""

if __name__ == '__main__':

    unittest.main(verbosity=1)
    

