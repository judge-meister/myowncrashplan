#!/usr/bin/env python

import unittest, sys
from unittest.mock import patch, mock_open
import os, shutil, socket
from io import StringIO
import logging
import json
import getpass
from subprocess import getstatusoutput as unix

from RsyncMethod import RsyncMethod
from Settings import Settings, default_settings_json
from RemoteComms import RemoteComms
from MetaData import MetaData
from CrashPlan import CrashPlan
from CrashPlanError import CrashPlanError
from Utils import process


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
        #print(val)

class FakeRemoteComms(RemoteComms):
    def __init__(self, settings, log):
        # hijacking input
        self.filename = ""
        self.status = settings
        self.message = log
        pass
        
    def remoteCommand(self, cmd):
        return self.status, self.message

    def remoteCopy(self, filename):
        self.filename = filename
        
    def getFilename(self):
        return self.filename
        
    def getBackupList(self):
        return ['one','two']
        
class FakeMetaDataSettings(Settings):
    def __init__(self, path, log):
        self.stuff = {'backup-destination':'',
                      'local-hostname':'',
                      'settings-dir':''}
    def __call__(self, key):
        return self.stuff[key]
    def set(self, key, val):
        self.stuff[key] = val
        


#with patch("builtins.open", mock_open(read_data="data")) as mock_file:
#    assert open("path/to/open").read() == "data"
#    mock_file.assert_called_with("path/to/open")
#[call('/Users/judge/.metadata', 'w'),
# call().__enter__(),
# call().write('{"backup-today": "2019-01-02", "latest-complate": "2019-01-02-012345", "latest-complete": ""}\n'),
# call().__exit__(None, None, None)]

    




        
class FakeMetaData(MetaData):
    def __init__(self, log, comms, settings, jstr):
        self.meta={'backup-today':'2019-01-01', 'latest-complete':'2019-01-01-012345'}
    def get(self, key):
        return self.meta[key]
        
class FakeCrashPlanSettings(Settings):
    def __init__(self, path, log):
        self.stuff = {'backup-destination':'',
                      'local-hostname':'',
                      'settings-dir':''}
    def __call__(self, key):
        return self.stuff[key]
    def set(self, key, val):
        self.stuff[key] = val

class TestRsyncMethod(unittest.TestCase):
    """"""
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

    def test_constructor(self):
        rsync = RsyncMethod(self.settings, self.meta, self.log, self.comms, False)

    def test_buildCommand(self):
        """"""
        rsync = RsyncMethod(self.settings, self.meta, self.log, self.comms, False)
        rsync.settings.set("backup-destination", '/tmp')
        rsync.buildCommand("/Users/judge", "/zdata/myowncrashplan/Prometheus.local/WORKING")
        self.assertEqual(rsync.cmd, 'rsync -av --link-dest=../two --bwlimit=2500 --timeout=300 --delete --delete-excluded  --exclude-from=/Users/judge/test_myocp/myocp_excl /Users/judge "15.0.0.1:/zdata/myowncrashplan/Prometheus.local/WORKING" ')

    def test_buildCommand_2(self):
        """"""
        rsync = RsyncMethod(self.settings, self.meta, self.log, self.comms, True)
        rsync.settings.set("backup-destination", '/tmp')
        rsync.buildCommand("/Users/judge", "/zdata/myowncrashplan/Prometheus.local/WORKING")
        self.assertEqual(rsync.cmd, 'rsync -av --dry-run --link-dest=../two --bwlimit=2500 --timeout=300 --delete --delete-excluded  --exclude-from=/Users/judge/test_myocp/myocp_excl /Users/judge "15.0.0.1:/zdata/myowncrashplan/Prometheus.local/WORKING" ')

if __name__ == '__main__':

    unittest.main(verbosity=1)
    