#!/usr/bin/env python

import unittest
from unittest.mock import patch


from myowncrashplan import (Log,
                            Settings,
                            RemoteComms,
                            MetaData,
                            CrashPlan,
                            CrashPlanError,
                            MountCommand)

class Testing(object):
    def __init__(self):
        self.setup()
        self.test02()
        self.test03()
        self.test04()
        self.test05()
        self.test01()
        

    def setup(self):
        self.settings = Settings(settings_json)
        self.comms = RemoteComms(self.settings)
        
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
        
    def test03(self):
        print("\nTEST 03")
        print("Testing Settings")
        print("Server is up %s" % self.comms.serverIsUp())
        js="""{"server-name": "skynet", "server-address": "192.168.0.77","myocp-debug": true, 
               "rsync-excludes-hidden": "", "rsync-excludes-folders": "", "myocp-tmp-dir": "",
               "rsync-exclude-file": "" }"""
        try:
            set2=Settings(js)
        except CrashPlanError as exc:
            print(exc)
        js="""{"server-name": "skynet", "server-address": "","myocp-debug": true, 
               "rsync-excludes-hidden": "", "rsync-excludes-folders": "", "myocp-tmp-dir": "",
               "rsync-exclude-file": "" }"""
        set2=Settings(js)
        com2=RemoteComms(set2)
        print("Server is up %s" % com2.serverIsUp())
        print("rsync-exclude-file = ",self.settings("rsync-exclude-file"))
        self.settings.create_excl_file()
        print(open(self.settings("rsync-exclude-file"), 'r').read())
        self.settings.remove_excl_file()
        self.settings.remove_excl_file()
        try:
            self.settings('Test-key')
        except CrashPlanError as exc:
            print(exc)
        js2="""{"test-key": "2" "test-key-2": True }"""
        try:
            set3=Settings(js2)
        except CrashPlanError as exc:
            print(exc)
        open("./temp.json", "w").write(js)
        set4=Settings("./temp.json")
        os.unlink("./temp.json")

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

    def test05(self):
        print("\nTEST 05")
        print("Testing MountCommand")
        mnt=MountCommand(self.settings)
        mnt.mount()
        mnt.umount()
        
    def test02(self):
        # TEST MetaData class and remote reading and writing
        print("\nTEST 02")
        print("Testing MetaData")
        print("Read Remote .metadata")
        json_str=""
        try:
            json_str = self.comms.readMetaData()
        except CrashPlanError as exc:
            print(exc)
        print(json_str)
        print("Create new instance of MetaData class")
        metadata = MetaData(json_str)
        try:
            print("%s = %s" % ('latest-complete', metadata.get('latest-complete')))
        except CrashPlanError as exc:
            print(exc)
        meta1=MetaData()
        meta1.set('backup-today', '2019-02-20')
        meta1.set('latest-complete', '2019-02-20-230000')
        print("Create new instance of MetaData class")
        js2 = repr(meta1)
        meta2 = MetaData(js2)
        print(meta2.get('backup-today'))
        print("Writing .metadata Remotely")
        try:
            self.comms.writeMetaData(repr(meta2))
        except CrashPlanError as exc:
            print(exc)
        try:
            st,rt = self.comms.remoteCommand("ls -la %s" % (os.path.join(self.settings('backup-destination'),self.settings('local-hostname'))))
            print(rt)
        except CrashPlanError as exc:
            print(exc)
        print("Invalid .metadata")
        try:
            meta3 = MetaData('{"test-key": "invalid"}')
        except CrashPlanError as exc:
            print(exc)
        try:
            meta2.get("test-key")
        except CrashPlanError as exc:
            print(exc)
        try:
            meta2.set("test-key", "21")
        except CrashPlanError as exc:
            print(exc)
        
class FakeLog(object):
    def __init__(self):
        self.val = ""
    def __call__(self, val):
        self.val = val
    def getVal(self):
        return val

class TestMetaData(unittest.TestCase):
    """"""
    @patch('myowncrashplan.Log')
    def test_metadata_set_exception(self, MockClass1):
        metadata = MetaData()
        with self.assertRaises(CrashPlanError) as cpe:
            metadata.set('test', 'test')
        
    @patch('myowncrashplan.Log')
    def test_metadata_constructor_fail(self, MockClass1):
        json_str="""{"test1": true}"""
        #with patch.object(Log, '__call__', )
        metadata = MetaData(json_str)
        assert MockClass1.called
        #assert MockClass1.getVal() == "(__init__)metadata does not have all the expected keys."

    @patch('myowncrashplan.Log')
    def test_metadata_get_exception(self, MockClass1):
        json_str="""{"backup-today": "", "latest-complete": ""}"""
        metadata = MetaData(json_str)
        with self.assertRaises(CrashPlanError) as cpe:
            metadata.get("test")
        
    @patch('myowncrashplan.Log')
    def test_metadata_get_success(self, MockClass1):
        json_str="""{"backup-today": "2019-01-02", "latest-complete": "2019-01-02-012345"}"""
        metadata = MetaData(json_str)
        self.assertEqual(metadata.get("backup-today"),"2019-01-02")

    @patch('myowncrashplan.Log')
    def test_metadata_set_success(self, MockClass1):
        json_str="""{"backup-today": "2019-01-02", "latest-complete": "2019-01-02-012345"}"""
        metadata = MetaData(json_str)
        metadata.set('backup-today', "2019-12-12")
        self.assertEqual(metadata.get("backup-today"),"2019-12-12")

    @patch('myowncrashplan.Log')
    def test_metadata__repr__success(self, MockClass1):
        json_str="""{"backup-today": "2019-01-02", "latest-complete": "2019-01-02-012345"}"""
        metadata = MetaData(json_str)
        metadata.set('backup-today', "2019-12-12")
        self.assertEqual(repr(metadata), '{"backup-today": "2019-12-12", "latest-complete": "2019-01-02-012345"}\n')

if __name__ == '__main__':
    #T1 = Testing()
    unittest.main()