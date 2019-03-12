# pylint: disable=invalid-name
# pylint: disable=missing-docstring
# pylint: disable=trailing-whitespace
# pylint: disable=trailing-newlines
# pylint: disable=line-too-long


import os
import shutil
import logging
import unittest

from unittest.mock import patch, mock_open
from Settings import Settings
from RemoteComms import RemoteComms
from MetaData import MetaData
from CrashPlanError import CrashPlanError


class FakeLog(logging.Logger):
    def __init__(self):
        self.val = {'info':[], 'debug':[], 'error':[]}

    def getVal(self, key):
        return "|".join(self.val[key])

    def info(self, val):
        self.val['info'].append(val)


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
        
        
class FakeMetaDataSettings(Settings):
    def __init__(self, path, log):
        self.stuff = {'backup-destination':'',
                      'local-hostname':'',
                      'settings-dir':''}
    def __call__(self, key):
        return self.stuff[key]
        
    def set(self, key, val):
        self.stuff[key] = val
        


class TestMetaData(unittest.TestCase):
    """Testing MetaData"""
    
    def setUp(self):
        self.log = FakeLog()
        self.settings = FakeMetaDataSettings(None, None)
        self.comms = FakeRemoteComms(0, '')
        
    def test_metadata_constructor(self):
        """verify __init__() creates an empty dict if no json is given"""
        metadata = MetaData(self.log, self.comms, self.settings)
        self.assertDictEqual(metadata.meta, {'backup-today':'', 'latest-complete':''})
        #self.assertEqual(self.log.getVal('info').split('|')[0], 'MetaData added missing expected key latest-complete.')
        #self.assertEqual(self.log.getVal('info').split('|')[1], 'MetaData added missing expected key backup-today.')
        self.assertEqual(self.log.getVal('info'), '')

    def test_metadata_set_exception(self):
        """verify set checks for invalid keys"""
        json_str = ""
        metadata = MetaData(self.log, self.comms, self.settings, json_str)
        self.assertDictEqual(metadata.meta, {'backup-today':'', 'latest-complete':''})
        with self.assertRaises(CrashPlanError) as cpe:
            metadata.set("test", "t")
            
        self.assertIsInstance(cpe.exception, CrashPlanError)
        self.assertEqual(repr(cpe.exception.value), "'(set) Invalid meta data key - test'")

        #self.assertEqual(self.log.getVal('info').split('|')[0], 'MetaData added missing expected key latest-complete.')
        #self.assertEqual(self.log.getVal('info').split('|')[1], 'MetaData added missing expected key backup-today.')
        self.assertEqual(self.log.getVal('info'), '')

    def test_metadata_get_exception(self):
        """verify get checks for invalid keys"""
        json_str = """{"backup-today": "", "latest-complete": ""}"""
        metadata = MetaData(self.log, self.comms, self.settings, json_str)
        with self.assertRaises(CrashPlanError) as cpe:
            metadata.get("test")

        self.assertIsInstance(cpe.exception, CrashPlanError)
        self.assertEqual(repr(cpe.exception.value), "'(get) Invalid meta data key - test'")

        self.assertEqual(self.log.getVal('info'), '')
        
    def test_metadata_get_success(self):
        """verify successful get call"""
        json_str = """{"backup-today": "2019-01-02", "latest-complete": "2019-01-02-012345"}"""
        metadata = MetaData(self.log, self.comms, self.settings, json_str)
        self.assertEqual(metadata.get("backup-today"), "2019-01-02")
        self.assertEqual(self.log.getVal('info'), '')

    def test_metadata_set_success(self):
        """verify successful setting of key,val pair"""
        json_str = """{"backup-today": "2019-01-02", "latest-complete": "2019-01-02-012345"}"""
        metadata = MetaData(self.log, self.comms, self.settings, json_str)
        metadata.set('backup-today', "2019-12-12")
        self.assertEqual(metadata.get("backup-today"), "2019-12-12")
        self.assertEqual(self.log.getVal('info'), '')

    def test_metadata__repr__success(self):
        """verify __repr__ returns as expected"""
        json_str = """{"backup-today": "2019-01-02", "latest-complate": "2019-01-02-012345"}"""
        metadata = MetaData(self.log, self.comms, self.settings, json_str)
        #self.assertEqual(self.log.getVal('info').split('|')[0], "MetaData added missing expected key latest-complete.")
        self.assertEqual(self.log.getVal('info').split('|')[0], "MetaData removed unexpected key latest-complate.")
        self.assertNotEqual(repr(metadata), '{"backup-today": "2019-01-02", "latest-complete": "2019-01-02-012345"}\n')

    def test_metadata_readMetaData_1(self):
        """verify readMetaData"""
        jstr = """{"backup-today": "2019-01-02", "latest-complete": "2019-01-02-012345"}"""
        os.makedirs(os.path.join(os.environ['HOME'], "temp_myocp"), mode=0o755, exist_ok=True)
        with open(os.path.join(os.environ['HOME'], "temp_myocp", ".metadata"), 'w') as fp:
            fp.write(jstr)
        metadata = MetaData(self.log, self.comms, self.settings)
        metadata.settings.set("settings-dir", "temp_myocp")
        self.assertDictEqual(metadata.meta, {"backup-today": "", "latest-complete": ""})
        metadata.readMetaData()
        self.assertDictEqual(metadata.meta, {"backup-today": "2019-01-02", "latest-complete": "2019-01-02-012345"})
        shutil.rmtree(os.path.join(os.environ['HOME'], "temp_myocp"))

    def test_metadata_readMetaData_2(self):
        """verify readMetaData return empty json string if no such file returned from remote call"""
        json_str = """{}"""
        metadata = MetaData(self.log, self.comms, self.settings, json_str)
        metadata.readMetaData()
        self.assertDictEqual(metadata.meta, {})

    def test_metadata_writeMetaData_1(self):
        """verify writeMetaData write a file and copies it remotely"""
        json_str = """{"backup-today": "2019-01-02", "latest-complete": "2019-01-02-012345"}"""
        metadata = MetaData(self.log, self.comms, self.settings, json_str)
        self.assertEqual(self.log.getVal('info'), '')
        with patch("builtins.open", mock_open(read_data="data")) as mock_file:
            metadata.writeMetaData()
            mock_file.assert_called_with('/Users/judge/.metadata', 'w')
            handle = mock_file()
            handle.write.assert_called_once_with('{"backup-today": "2019-01-02", "latest-complete": "2019-01-02-012345"}\n')

        self.assertEqual(self.comms.getFilename(), '/Users/judge/.metadata')
        
    def test_metadata_readRemoteMetaData_1(self):
        """verify readRemoteMetaData"""
        jstr = """{"backup-today": "2019-01-02", "latest-complete": "2019-01-02-012345"}"""
        fakecomms = FakeRemoteComms(0, jstr)
        metadata = MetaData(self.log, fakecomms, self.settings)
        self.assertEqual(metadata.readRemoteMetaData(), jstr)

    def test_metadata_readRemoteMetaData_2(self):
        """verify readRemoteMetaData return empty metadata on error"""
        #jstr = """{"backup-today": "2019-01-02", "latest-complete": "2019-01-02-012345"}"""
        fakecomms = FakeRemoteComms(1, "No such file or directory")
        metadata = MetaData(self.log, fakecomms, self.settings)
        self.assertEqual(metadata.readRemoteMetaData(), "{}")

if __name__ == '__main__':

    unittest.main(verbosity=1)
    