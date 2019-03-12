# pylint: disable=invalid-name
# pylint: disable=missing-docstring
# pylint: disable=trailing-whitespace
# pylint: disable=trailing-newlines
# pylint: disable=line-too-long
# pylint: disable=too-many-public-methods

import unittest
import os
import shutil
import socket
import logging
import json
from io import StringIO
from unittest.mock import patch

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

    def debug(self, val):
        self.val['debug'].append(val)

    def error(self, val):
        self.val['error'].append(val)
        #print(val)


class TestSettings(unittest.TestCase):
    """Test Settings"""

    def setUp(self):
        self.log = FakeLog()

    def test_settings_constructor(self):
        """verify params of __init__() are of the correct types"""
        with patch.object(Settings, 'verify', return_value=None) as mock_verify:
            with patch.object(Settings, 'load', return_value=None) as mock_load:
                settings = Settings("path", self.log)
        assert mock_verify.called
        assert mock_load.called

        self.assertIsInstance(settings.path, str)
        self.assertIsInstance(settings.log, logging.Logger)

    def test_settings_load_1(self):
        """verify that CrashPlanError is raised because of problems decoding Json string"""
        fp = open('test.json', 'w')
        fp.write('')
        fp.close()
        with self.assertRaises(CrashPlanError) as cpe:
            settings = Settings('test.json', self.log)
        
        self.assertIsInstance(cpe.exception.args[0], json.decoder.JSONDecodeError)
        self.assertEqual(repr(cpe.exception.value), "JSONDecodeError('Expecting value: line 1 column 1 (char 0)')")
        os.unlink('test.json')

    def test_settings_load_2(self):
        """verify minimal json is loaded from a file."""
        with open('test.json', 'w') as fp:
            fp.write('{}')
        with patch.object(Settings, 'verify', return_value=None) as mock_verify:
            settings = Settings('test.json', self.log)
        assert mock_verify.called
        self.assertEqual(self.log.getVal('info'), "Settings file loaded.")
        self.assertDictEqual(settings.settings, {})
        os.unlink('test.json')

    def test_settings_load_3(self):
        """verify minimal json is loaded from a string."""
        jstr = """{}"""
        with patch.object(Settings, 'verify', return_value=None) as mock_verify:
            settings = Settings(jstr, self.log)
        assert mock_verify.called
        self.assertEqual(self.log.getVal('info'), "Settings file loaded.")
        self.assertDictEqual(settings.settings, {})

    @patch('sys.stdout', new_callable=StringIO)
    def test_settings_load_4(self, mock_stdout):
        """verify json with some content is loaded and as debug it set values are printed."""
        jstr = """{"debug-level": true}"""
        with patch.object(Settings, 'verify', return_value=None) as mock_verify:
            settings = Settings(jstr, self.log)
        assert mock_verify.called
        self.assertEqual(self.log.getVal('info'), "Settings file loaded.")
        self.assertDictEqual(settings.settings, {"debug-level": True})
        self.assertEqual(self.log.getVal('debug'), "settings[debug-level] : True")
        self.assertEqual(mock_stdout.getvalue(), "Settings Loaded.\n")

    def test_settings_set_1(self):
        """verify a new settings key,val pair can be set"""
        jstr = """{}"""
        with patch.object(Settings, 'verify', return_value=None) as mock_verify:
            settings = Settings(jstr, self.log)
        assert mock_verify.called
        settings.set("test", 21)
        self.assertDictEqual(settings.settings, {"test": 21})

    def test_settings_remove_1(self):
        """verify a key,val pair can be removed from the settings"""
        jstr = """{"debug-level": false}"""
        with patch.object(Settings, 'verify', return_value=None) as mock_verify:
            settings = Settings(jstr, self.log)
        assert mock_verify.called
        self.assertDictEqual(settings.settings, {"debug-level": False})
        settings.remove("debug-level")
        self.assertDictEqual(settings.settings, {})
        with self.assertRaises(KeyError) as cpe:
            self.assertEqual(settings.settings['debug-level'], False)

    def test_settings_remove_2(self):
        """verify that attempting to remove non-existent key fails silently"""
        jstr = """{"debug-level": false}"""
        with patch.object(Settings, 'verify', return_value=None) as mock_verify:
            settings = Settings(jstr, self.log)
        assert mock_verify.called
        self.assertDictEqual(settings.settings, {"debug-level": False})
        settings.remove("myocp")
        self.assertDictEqual(settings.settings, {"debug-level": False})

    def test_settings__call__1(self):
        """verify settings in callable and returns a val for a given key"""
        jstr = """{"debug-level": false}"""
        with patch.object(Settings, 'verify', return_value=None) as mock_verify:
            settings = Settings(jstr, self.log)
        assert mock_verify.called
        self.assertDictEqual(settings.settings, {"debug-level": False})
        self.assertEqual(settings("debug-level"), False)

    def test_settings__call__2(self):
        """verify a CrashPlanError is raised if settings called with non-existent key"""
        jstr = """{"debug-level": false}"""
        with patch.object(Settings, 'verify', return_value=None) as mock_verify:
            settings = Settings(jstr, self.log)
        assert mock_verify.called
        self.assertDictEqual(settings.settings, {"debug-level": False})
        with self.assertRaises(CrashPlanError) as cpe:
            self.assertEqual(settings("myocp"), True)

    def test_settings_write_1(self):
        """verify settings file can be written"""
        jstr = """{
    "debug-level": false,
    "rsync-exclude-file": "test.excl",
    "rsync-excludes-folders": "1,2,3"
}"""
        with patch.object(Settings, 'verify', return_value=None) as mock_verify:
            settings = Settings(jstr, self.log)
        assert mock_verify.called
        self.assertEqual(self.log.getVal('info').split('|')[0], 'Settings file loaded.')
        self.assertDictEqual(settings.settings, {"rsync-exclude-file": "test.excl", "rsync-excludes-folders": "1,2,3", "debug-level": False})
        self.assertFalse(os.path.exists('test_1/test.json'))
        settings.write('test_1/test.json')
        self.assertTrue(os.path.exists('test_1/test.json'))
        with open('test_1/test.json', 'r') as fp:
            self.assertEqual(fp.read(), jstr)
        shutil.rmtree('test_1')

    def test_settings_verify_1(self):
        """verify that verify fails when there are missing keys"""
        jstr = """{ "debug-level": false,
            "exclude-files": "",
            "exclude-folders": "",
            "settings-dir": "test_myocp",
            "extra-backup-sources": "1,2",
            "maximum-used-percent": 90
        }"""
        with self.assertRaises(CrashPlanError) as cpe:
            settings = Settings(jstr, self.log)
            
        self.assertIsInstance(cpe.exception, CrashPlanError)
        self.assertEqual(repr(cpe.exception.value), "'ERROR(Settings.verify(): Problems verifying settings file.'")
            
        self.assertEqual(self.log.getVal('error').split('|')[0], 'expected key server-name not found in settings file.')
        self.assertEqual(self.log.getVal('error').split('|')[1], 'Problems verifying Settings file. There are some essential settings missing.')
        self.assertEqual(self.log.getVal('info'), 'Settings file loaded.')


    def test_settings_verify_2(self):
        """verify that verify fails when unexpected keys are in the settings file"""
        jstr = """{ "debug-level": false,
            "exclude-files": "",
            "exclude-folders": "",
            "rsync-excludes-list": "",
            "settings-dir": "test_myocp",
            "extra-backup-sources": "",
            "maximum-used-percent": 90,
            "server-name": ""
        }"""
        with self.assertRaises(CrashPlanError) as cpe:
            settings = Settings(jstr, self.log)
            
        self.assertIsInstance(cpe.exception, CrashPlanError)
        self.assertEqual(repr(cpe.exception.value), "'ERROR(Settings.verify(): Problems verifying settings file.'")

        self.assertEqual(self.log.getVal('error').split('|')[0], 'unexpected key rsync-excludes-list found in settings file.')
        self.assertEqual(self.log.getVal('error').split('|')[1], 'Problems verifying Settings file. There are some essential settings missing.')

        self.assertEqual(self.log.getVal('info'), 'Settings file loaded.')

    def test_settings_verify_3(self):
        """verify that verify fails in server-name is empty"""
        jstr = """{ "debug-level": false,
            "exclude-files": "",
            "exclude-folders": "",
            "settings-dir": "test_myocp",
            "extra-backup-sources": "1,2",
            "maximum-used-percent": 90,
            "server-address": "127.0.0.1",
            "server-name": ""
        }"""
        with patch.object(os, 'makedirs', return_value=None) as mock_mkdir:
            with self.assertRaises(CrashPlanError) as cpe:
                settings = Settings(jstr, self.log)
        assert mock_mkdir.called

        self.assertIsInstance(cpe.exception, CrashPlanError)
        self.assertEqual(repr(cpe.exception.value), "'ERROR(Settings.verify(): server-name is empty.'")

        self.assertEqual(self.log.getVal('error'), '')
        self.assertEqual(self.log.getVal('info'), 'Settings file loaded.')


    @patch('os.makedirs')
    def test_settings_verify_4(self, mock_mkdir):
        """verify that verify responds correctly to hostname errors"""
        jstr = """{ "debug-level": false,
            "exclude-files": "",
            "exclude-folders": "",
            "settings-dir": "test_myocp",
            "extra-backup-sources": "1,2",
            "maximum-used-percent": 90,
            "server-address": "15.0.0.1",
            "server-name": "myhost"
        }"""
        with self.assertRaises(CrashPlanError) as cpe:
            settings = Settings(jstr, self.log)

        self.assertIsInstance(cpe.exception, CrashPlanError)
        self.assertEqual(repr(cpe.exception.value), "'ERROR(Settings.verify(): server myhost not available on network.'")
        self.assertEqual(repr(self.log.val['error']), "[gaierror(8, 'nodename nor servname provided, or not known')]")
        assert mock_mkdir.called
        
        with patch.object(socket, 'gethostbyname', return_value='15.0.0.1') as mock_method:
            settings = Settings(jstr, self.log)
        assert mock_method.called
            
        with patch.object(socket, 'gethostbyname', return_value='15.0.0.2') as mock_method:
            with self.assertRaises(CrashPlanError) as cpe:
                settings = Settings(jstr, self.log)
        assert mock_method.called

        self.assertIsInstance(cpe.exception, CrashPlanError)
        self.assertEqual(repr(cpe.exception.value), "'ERROR(Settings.verify(): Server name and Address do not match.'")

    @patch('os.makedirs')
    def test_settings_verify_5(self, mock_mkdir):
        """verify that verify completes its verification with 2 extra backup dirs"""
        jstr = """{ "debug-level": false,
            "exclude-files": "",
            "exclude-folders": "",
            "settings-dir": "test_myocp",
            "extra-backup-sources": "1,2",
            "maximum-used-percent": 90,
            "server-address": "",
            "server-name": "myhost"
        }"""
        with patch.object(socket, 'gethostbyname', return_value='15.0.0.1') as mock_ghbn:
            with patch.object(socket, 'gethostname', return_value='Fred.local') as mock_ghn:
                settings = Settings(jstr, self.log)
        assert mock_mkdir.called
        assert mock_ghbn.called
        assert mock_ghn.called
            
        self.assertEqual(self.log.getVal('info').split('|')[0], 'Settings file loaded.')
        self.assertEqual(self.log.getVal('info').split('|')[1], 'Settings file verified.')

        #self.assertFalse(settings('rsync-options').find('--quiet'))
        #self.assertTrue(settings('rsync-options').find('--bwlimit'))
        #self.assertListEqual(settings('rsync-excludes-list'), ['.a','.b','c','d'])
        self.assertEqual(settings('settings-dir'), os.path.join(os.environ['HOME'], "test_myocp"))
        #self.assertEqual(settings('rsync-exclude-file'), os.path.join(settings('settings-dir'), "test.excl"))
        #self.assertEqual(settings('rsync-exclude-file-option'), "--exclude-from=%s" % settings('rsync-exclude-file'))
        self.assertListEqual(settings('extra-backup-sources-list'), ['1', '2'])
        self.assertEqual(settings('server-name'), 'myhost')
        self.assertEqual(settings('server-address'), '15.0.0.1')
        self.assertEqual(settings('local-hostname'), 'Fred.local')

    @patch('os.makedirs')
    def test_settings_verify_6(self, mock_mkdir):
        """verify that verify completes its verification with 1 extra backup dir"""
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
            settings = Settings(jstr, self.log)
        assert mock_mkdir.called
        assert mock_method.called
            
        self.assertEqual(self.log.getVal('info').split('|')[0], 'Settings file loaded.')
        self.assertEqual(self.log.getVal('info').split('|')[1], 'Settings file verified.')

        self.assertListEqual(settings('extra-backup-sources-list'), ['1'])

if __name__ == '__main__':

    unittest.main(verbosity=1)
    