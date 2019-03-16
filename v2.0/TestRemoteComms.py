# pylint: disable=invalid-name
# pylint: disable=missing-docstring
# pylint: disable=trailing-whitespace
# pylint: disable=trailing-newlines
# pylint: disable=line-too-long
# pylint: disable=too-many-public-methods

import os
import logging
import getpass
import unittest

from subprocess import getstatusoutput as unix
from Settings import Settings
from RemoteComms import RemoteComms
from CrashPlanError import CrashPlanError


class FakeLog(logging.Logger):
    def __init__(self):
        self.val = {'info':[], 'debug':[], 'error':[]}

    def getVal(self, key):
        return "|".join(self.val[key])

    def info(self, val):
        self.val['info'].append(val)

    def error(self, val):
        self.val['error'].append(val)


# Only run this test as me as it relies on my local environment
# It uses the current settings.json file in ~/.myocp/
# It makes actual changes to file in the server.
# Some of the server responses may change over time which would make the test fail
@unittest.skipIf(getpass.getuser() != 'judge', 
                 "My local environment is influential in this test passing.")
class TestRemoteComms(unittest.TestCase):
    """Test RemoteComms"""
    
    def setUp(self):
        log = FakeLog()
        settings = Settings(os.path.join(os.environ['HOME'], '.myocp', 'settings.json'), log)
        self.remote = RemoteComms(settings, log)

    def tearDown(self):
        """remove files created on server"""
        unix("ssh skynet rm -rf /tmp/spam2.log")
        unix("ssh skynet rm -rf /tmp/fred")
        
    def test_remote_comms_host_up(self):
        """verify hostIsUp and serverIsUp"""
        remote = self.remote
    
        self.assertTrue(remote.hostIsUp('Prometheus'))
        self.assertFalse(remote.hostIsUp('raspberrypi'))
        self.assertTrue(remote.serverIsUp())

    def test_remote_comms_get_info_from_server(self):
        """verify remoteSpace and getBackupList"""
        remote = self.remote

        space = remote.remoteSpace() # gives a percent space used
        self.assertGreater(space, 0)
        self.assertLessEqual(space, 100)
        self.assertGreater(len(remote.getBackupList()), 1)

    def test_remote_comms_command_fail(self):
        """verify fail response from remoteCommand"""
        remote = self.remote

        st, rt = remote.remoteCommand("ls /root")
        self.assertEqual(st, 2)
        self.assertEqual(rt, 'ls: cannot open directory \'/root\': Permission denied')

    def test_remote_comms_remoteCopy_2(self):
        """verify remoteCopy with 2 params"""
        remote = self.remote

        remote.settings.set("backup-destination", '/tmp')
        remote.settings.set("local-hostname", "")

        remote.remoteCopy('spam.log', 'spam2.log')
        st, rt = remote.remoteCommand("ls -l /tmp/spam2.log")
        self.assertEqual(st, 0)
        self.assertEqual(rt[:30], '-rw-r--r-- 1 judge judge 1271 ')
        self.assertEqual(rt[43:57], '/tmp/spam2.log')

        # tidyup
        st, rt = remote.remoteCommand("rm -rf /tmp/spam2.log")
        self.assertEqual(st, 0)
        self.assertEqual(rt, '')
        

    def test_remote_comms_remoteCopy_1(self):
        """verify remoteCopy with 1 param"""
        remote = self.remote

        remote.settings.set("backup-destination", '/tmp')
        remote.settings.set("local-hostname", "fred")

        remote.log.val['error'] = []
        with self.assertRaises(CrashPlanError) as cpe:
            remote.remoteCopy('/Users/judge/Development/Projects/myowncrashplan/v2.0/spam.log')

        self.assertIsInstance(cpe.exception, CrashPlanError)
        self.assertEqual(repr(cpe.exception.value), "\"ERROR: remote command failed. (['scp', '/Users/judge/Development/Projects/myowncrashplan/v2.0/spam.log', '192.168.0.7:/tmp/fred/spam.log'])\"")
        
        self.assertEqual(remote.log.getVal('error').split('|')[0], "(remoteCommand): ['scp', '/Users/judge/Development/Projects/myowncrashplan/v2.0/spam.log', '192.168.0.7:/tmp/fred/spam.log']")
        self.assertEqual(remote.log.getVal('error').split('|')[1], "(remoteCommand): 1 scp: /tmp/fred/spam.log: No such file or directory")
    
        st, rt = remote.remoteCommand("ls -l /tmp/fred/spam.log")
        self.assertEqual(st, 2)
        self.assertEqual(rt, 'ls: cannot access \'/tmp/fred/spam.log\': No such file or directory')
        
        remote.createRootBackupDir()
        st, rt = remote.remoteCommand("ls -l /tmp/fred")
        self.assertEqual(st, 0)
        self.assertEqual(rt, 'total 0')
        
        remote.remoteCopy('/Users/judge/Development/Projects/myowncrashplan/v2.0/spam.log')
        st, rt = remote.remoteCommand("ls -l /tmp/fred/spam.log")
        self.assertEqual(st, 0)
        self.assertEqual(rt[:30], '-rw-r--r-- 1 judge judge 1271 ')
        self.assertEqual(rt[43:62], '/tmp/fred/spam.log')

        # tidyup
        st, rt = remote.remoteCommand("rm -rf /tmp/fred")
        self.assertEqual(st, 0)
        self.assertEqual(rt, '')

if __name__ == '__main__':

    unittest.main(verbosity=1)
    