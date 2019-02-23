#!/usr/bin/env python

import unittest
from unittest.mock import patch
import os, shutil
from io import StringIO

from myowncrashplan import (Log,
                            Settings,
                            RemoteComms,
                            MetaData,
                            CrashPlan,
                            CrashPlanError,
                            MountCommand)

class Testing(object):
    def __init__(self):
        pass
        
    def run(self):
        self.setup()
        #self.test02()
        #self.test03()
        self.test04()
        self.test04a()
        self.test01()
        

    def setup(self):
        self.errlog = Log(os.path.join(os.environ['HOME'],".myocp/test.log"))
        self.settings = Settings(os.path.join(os.environ['HOME'],".myocp/settings.json"), self.errlog)
        self.comms = RemoteComms(self.settings, self.errlog)
        
    def test01(self):
        print("\nTEST 01")
        print("Testing CrashPlan")
        dry_run = True
        try:
            CP = CrashPlan(self.settings, self.comms, dry_run)
        except CrashPlanError as exc:
            print(exc)
            #CP.meta = MetaData()
            #CP.meta.set('backup-today', '2019-02-20')
            #CP.meta.set('latest-complete', '2019-02-20-230000')
            
        print(CP.rsyncCmd())
        CP.backupSuccessful = False
        CP.finishUp()
        CP.backupSuccessful = True
        CP.finishUp()
        

    def test04a(self):
        print("\nTEST 04a")
        st, rt = self.comms.remoteCommand("ls -trd /zdata/myowncrashplan/Prometheus.local/2019-02-03*")
        print(st, rt)
        lst = rt.split('\n')
        print("Basename: ",os.path.basename(lst[0]))
        st, rt = self.comms.remoteCommand("ls -trd /zdata/myowncrashplan/Prometheus.local/3*")
        print(st, rt)
        if st != 0:
            print([])

    def test04(self):
        print("\nTEST 04")
        print("Testing RemoteComms")
        try:
            print(self.comms.remoteSpace())
        except (CrashPlanError, ValueError) as exc:
            print(exc)
        try:
            print(self.comms.getBackupList())
        except CrashPlanError as exc:
            print(exc)
        try:
            self.comms.removeOldestBackup("oldest")
        except CrashPlanError as exc:
            print(exc)
        try:
            print("CreateRootBackup()q",self.comms.createRootBackupDir())
        except CrashPlanError as exc:
            print(exc)
        try:
            self.comms.remoteCommand("hello")
        except CrashPlanError as exc:
            print(exc)
        try:
            self.comms.remoteCopy("hello")
        except CrashPlanError as exc:
            print(exc)
        js="""{"server-name": "sky", "server-address": "192.168.0.77","myocp-debug": true, 
               "rsync-excludes-hidden": "", "rsync-excludes-folders": "", "myocp-tmp-dir": "",
               "rsync-exclude-file": "" }"""
        set2=Settings(js)
        com2=RemoteComms(set2)
        print("Server is up %s" % com2.serverIsUp())

        
class FakeLog(Log):
    def __init__(self):
        self.val = ""
    def __call__(self, val):
        self.val = val
        print(val)
    def getVal(self):
        return self.val

class TestMetaData(unittest.TestCase):
    """"""
    def setUp(self):
        self.log = FakeLog()
        
    def test_metadata_constructor(self):
        metadata = MetaData(self.log)
        self.assertEqual({},metadata.meta)
        
    def test_metadata_set_exception(self):
        json_str=""
        metadata = MetaData(self.log, json_str)
        with self.assertRaises(CrashPlanError) as cpe:
            metadata.set("test", "t")

    def test_metadata_get_exception(self):
        json_str="""{"backup-today": "", "latest-complete": ""}"""
        metadata = MetaData(self.log, json_str)
        with self.assertRaises(CrashPlanError) as cpe:
            metadata.get("test")
        
    def test_metadata_get_success(self):
        json_str="""{"backup-today": "2019-01-02", "latest-complete": "2019-01-02-012345"}"""
        metadata = MetaData(self.log, json_str)
        self.assertEqual(metadata.get("backup-today"),"2019-01-02")

    def test_metadata_set_success(self):
        json_str="""{"backup-today": "2019-01-02", "latest-complete": "2019-01-02-012345"}"""
        metadata = MetaData(self.log, json_str)
        metadata.set('backup-today', "2019-12-12")
        self.assertEqual(metadata.get("backup-today"),"2019-12-12")

    @patch('sys.stdout', new_callable=StringIO)
    def test_metadata__repr__success(self, mock_stdout):
        json_str="""{"backup-today": "2019-01-02", "latest-complate": "2019-01-02-012345"}"""
        metadata = MetaData(self.log, json_str)
        self.assertEqual(self.log.getVal(), "(__init__)metadata does not have all the expected keys.")
        self.assertEqual(mock_stdout.getvalue(),"(__init__)metadata does not have all the expected keys.\n")
        self.assertNotEqual(repr(metadata), '{"backup-today": "2019-01-02", "latest-complete": "2019-01-02-012345"}\n')

class TestSettings(unittest.TestCase):
    """"""
    def setUp(self):
        self.log = FakeLog()

    @patch('myowncrashplan.Settings.load')
    @patch('myowncrashplan.Settings.verify')
    def test_settings_constructor(self, mock_verify, mock_load):
        setting = Settings("path", self.log)

    @patch('sys.stdout', new_callable=StringIO)
    @patch('myowncrashplan.Settings.verify')
    def test_settings_load_1(self, mock_verify, mock_stdout):
        fp = open('test.json', 'w')
        fp.write('')
        fp.close()
        with self.assertRaises(CrashPlanError) as cpe:
            settings = Settings('test.json', self.log)
        self.assertEqual(mock_stdout.getvalue(), "ERROR(load_settings()): problems loading settings file (Expecting value: line 1 column 1 (char 0))\n")
        os.unlink('test.json')

    @patch('sys.stdout', new_callable=StringIO)
    @patch('myowncrashplan.Settings.verify')
    def test_settings_load_2(self, mock_verify, mock_stdout):
        with open('test.json', 'w') as fp:
            fp.write('{}')
        #fp.close()
        settings = Settings('test.json', self.log)
        self.assertEqual(mock_stdout.getvalue(), "Settings file loaded.\n")
        os.unlink('test.json')

    @patch('sys.stdout', new_callable=StringIO)
    @patch('myowncrashplan.Settings.verify')
    def test_settings_load_3(self, mock_verify, mock_stdout):
        jstr = """{}"""
        settings = Settings(jstr, self.log)
        self.assertEqual(self.log.getVal(),"Settings file loaded.")
        self.assertEqual(mock_stdout.getvalue(), "Settings file loaded.\n")

    @patch('sys.stdout', new_callable=StringIO)
    @patch('myowncrashplan.Settings.verify')
    def test_settings_load_4(self, mock_verify, mock_stdout):
        jstr = """{"myocp-debug": true}"""
        settings = Settings(jstr, self.log)
        self.assertEqual(mock_stdout.getvalue(), "Settings file loaded.\nSettings Loaded.\nsettings[myocp-debug] : True\n")

    @patch('sys.stdout', new_callable=StringIO)
    @patch('myowncrashplan.Settings.verify')
    def test_settings_set_1(self, mock_verify, mock_stdout):
        jstr = """{"myocp-debug": true}"""
        settings = Settings(jstr, self.log)
        self.assertEqual(mock_stdout.getvalue(), "Settings file loaded.\nSettings Loaded.\nsettings[myocp-debug] : True\n")
        settings.set("test", 21)
        self.assertEqual(settings.settings['test'], 21)

    @patch('sys.stdout', new_callable=StringIO)
    @patch('myowncrashplan.Settings.verify')
    def test_settings_remove_1(self, mock_verify, mock_stdout):
        jstr = """{"myocp-debug": true}"""
        settings = Settings(jstr, self.log)
        self.assertEqual(mock_stdout.getvalue(), "Settings file loaded.\nSettings Loaded.\nsettings[myocp-debug] : True\n")
        settings.remove("myocp-debug")
        with self.assertRaises(KeyError) as cpe:
            self.assertEqual(settings.settings['myocp-debug'], True)

    @patch('sys.stdout', new_callable=StringIO)
    @patch('myowncrashplan.Settings.verify')
    def test_settings_remove_2(self, mock_verify, mock_stdout):
        jstr = """{"myocp-debug": true}"""
        settings = Settings(jstr, self.log)
        self.assertEqual(mock_stdout.getvalue(), "Settings file loaded.\nSettings Loaded.\nsettings[myocp-debug] : True\n")
        settings.remove("myocp")
        self.assertEqual(settings.settings['myocp-debug'], True)

    @patch('sys.stdout', new_callable=StringIO)
    @patch('myowncrashplan.Settings.verify')
    def test_settings__call__1(self, mock_verify, mock_stdout):
        jstr = """{"myocp-debug": true}"""
        settings = Settings(jstr, self.log)
        self.assertEqual(mock_stdout.getvalue(), "Settings file loaded.\nSettings Loaded.\nsettings[myocp-debug] : True\n")
        self.assertEqual(settings("myocp-debug"), True)

    @patch('sys.stdout', new_callable=StringIO)
    @patch('myowncrashplan.Settings.verify')
    def test_settings__call__2(self, mock_verify, mock_stdout):
        jstr = """{"myocp-debug": true}"""
        settings = Settings(jstr, self.log)
        self.assertEqual(mock_stdout.getvalue(), "Settings file loaded.\nSettings Loaded.\nsettings[myocp-debug] : True\n")
        with self.assertRaises(CrashPlanError) as cpe:
            self.assertEqual(settings("myocp"), True)

    @patch('os.unlink')
    @patch('sys.stdout', new_callable=StringIO)
    @patch('myowncrashplan.Settings.verify')
    def test_settings_remove_excl_file_1(self, mock_verify, mock_stdout, mock_unlink):
        jstr = """{"myocp-debug": true}"""
        settings = Settings(jstr, self.log)
        settings.remove_excl_file()
        self.assertEqual(mock_stdout.getvalue(), "Settings file loaded.\nSettings Loaded.\nsettings[myocp-debug] : True\nrsync exclusions file does not exist.\n")

    @patch('sys.stdout', new_callable=StringIO)
    @patch('myowncrashplan.Settings.verify')
    def test_settings_remove_excl_file_2(self, mock_verify, mock_stdout):
        jstr = """{"rsync-exclude-file": "test.excl"}"""
        with open('test.excl', 'w') as fp:
            fp.write('{}')
        settings = Settings(jstr, self.log)
        settings.remove_excl_file()
        self.assertEqual(mock_stdout.getvalue(), "Settings file loaded.\nrsync exclusions file removed.\n")
        self.assertNotEqual(os.path.exists('test.excl'), True)

    @patch('sys.stdout', new_callable=StringIO)
    @patch('myowncrashplan.Settings.verify')
    def test_settings_create_excl_file_1(self, mock_verify, mock_stdout):
        jstr = """{"rsync-exclude-file": "test.excl",
                   "rsync-excludes-list": "1,2,3",
                   "myocp-debug": false
               }"""
        settings = Settings(jstr, self.log)
        settings.create_excl_file()
        self.assertEqual(mock_stdout.getvalue(), "Settings file loaded.\nrsync exclusions file created at test.excl\n")
        os.unlink("test.excl")

    @patch('sys.stdout', new_callable=StringIO)
    @patch('myowncrashplan.Settings.verify')
    def test_settings_create_excl_file_2(self, mock_verify, mock_stdout):
        jstr = """{
    "myocp-debug": false,
    "rsync-exclude-file": "test.excl",
    "rsync-excludes-list": "1,2,3"
}"""
        settings = Settings(jstr, self.log)
        settings.write('test_1/test.json')
        with open('test_1/test.json', 'r') as fp:
            self.assertEqual(fp.read(), jstr)
        shutil.rmtree('test_1')

    @patch('sys.stdout', new_callable=StringIO)
    def test_settings_create_excl_verify_1(self, mock_stdout):
        jstr = """{ "myocp-debug": false }"""
        settings = Settings(jstr, self.log)

    @patch('sys.stdout', new_callable=StringIO)
    def test_settings_create_excl_verify_2(self, mock_stdout):
        jstr = """{ "myocp-debug": false,
            "rsync-excludes-hidden": "",
            "rsync-excludes-folders": "",
            "rsync-exclude-file": "test.excl",
            "myocp-tmp-dir": "test_myocp",
            "backup-sources-extra": "",
            "server-name": ""
        }"""
        settings = Settings(jstr, self.log)
        shutil.rmtree(os.path.join(os.environ['HOME'],"test_myocp"))

    @patch('sys.stdout', new_callable=StringIO)
    def test_settings_create_excl_verify_3(self, mock_stdout):
        jstr = """{ "myocp-debug": false,
            "rsync-excludes-hidden": "",
            "rsync-excludes-folders": "",
            "rsync-exclude-file": "test.excl",
            "myocp-tmp-dir": "test_myocp",
            "backup-sources-extra": "1,2",
            "server-address": "127.0.0.1",
            "server-name": ""
        }"""
        with self.assertRaises(CrashPlanError) as cpe:
            settings = Settings(jstr, self.log)
        shutil.rmtree(os.path.join(os.environ['HOME'],"test_myocp"))

    @patch('sys.stdout', new_callable=StringIO)
    def test_settings_create_excl_verify_4(self, mock_stdout):
        jstr = """{ "myocp-debug": false,
            "rsync-excludes-hidden": "",
            "rsync-excludes-folders": "",
            "rsync-exclude-file": "test.excl",
            "myocp-tmp-dir": "test_myocp",
            "backup-sources-extra": "1,2",
            "server-address": "15.0.0.1",
            "server-name": "myhost"
        }"""
        #with self.assertRaises(CrashPlanError) as cpe:
        settings = Settings(jstr, self.log)
        shutil.rmtree(os.path.join(os.environ['HOME'],"test_myocp"))


class TestRemoteComms(unittest.TestCase):
    """"""
    def setUp(self):
        self.log = FakeLog()

class TestCrashPlan(unittest.TestCase):
    """"""
    def setUp(self):
        self.log = FakeLog()


if __name__ == '__main__':
    #T1 = Testing()
    #T1.run()
    #T1.setup()
    #T1.test04a()
    unittest.main()
    