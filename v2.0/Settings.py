# pylint: disable=invalid-name
# pylint: disable=missing-docstring
# pylint: disable=trailing-whitespace
# pylint: disable=trailing-newlines

import os
import json
import logging
import socket
from CrashPlanError import CrashPlanError

default_settings_json = """
{
    "server-name": "",
    "server-address": "",
    "backup-destination": "",
    "backup-destination-uses-hostname": true, 
    "extra-backup-sources": "",
    "logfilename": "myowncrashplan.log",
    "exclude-files": ".AppleDB,.AppleDesktop,.AppleDouble,:2e*,.DS_Store,._*,.Trashes,.Trash,.fseventsd,.bzvol,.cocoapods",
    "exclude-folders": "lost+found,Network Trash Folder,Temporary Items,Saved Application State,Library,Parallels,VirtualBoxVMs,VirtualBox VMs",
    "debug-level": 0,
    "settings-dir": ".myocp",
    "maximum-used-percent" : 90
}
"""


class Settings():
    """Settings object"""
    
    def __init__(self, path, log):
        """"""
        assert isinstance(log, logging.Logger)
        assert isinstance(path, str)

        self.path = path
        self.log = log
        self.load()
        self.verify()
        
    def load(self):
        """load settings file """
        try:
            if os.path.exists(self.path):
                with open(self.path, 'r') as fp:
                    self.settings = json.load(fp)
            else:
                # use path as a string initially
                self.settings = json.loads(self.path)

            self.log.info("Settings file loaded.")
        except json.decoder.JSONDecodeError as exc:
            #print("ERROR(load_settings()): problems loading settings file (%s)" % exc)
            self.log.error("ERROR(load_settings()): problems loading settings file (%s)" % exc)
            #sys.exit(1)
            raise CrashPlanError(exc)

        else:
            if 'debug-level' in self.settings and self.settings['debug-level'] > 0:
                print("Settings Loaded.")

                for k in self.settings:
                    self.log.debug("settings[%s] : %s" % (k, self.settings[k]))
        
    def write(self, filename):
        """write the settins.json file"""
        if not os.path.exists(os.path.dirname(filename)):
            os.makedirs(os.path.dirname(filename))

        json_str = json.dumps(self.settings, sort_keys=True, indent=4)

        with open(filename, "w") as fp:
            fp.write(json_str)

    # pylint: disable=too-many-branches
    def verify(self):
        """verify settings are consistent"""
        expected_keys = ['exclude-files', 'exclude-folders', 'settings-dir',
                         'extra-backup-sources', 'server-name', 'maximum-used-percent']
        unexpected_keys = ['rsync-excludes-list']
        
        keys_missing = False
        invalid_key = False

        for key in expected_keys:

            if key not in self.settings:
                self.log.error(f"expected key {key} not found in settings file.")
                keys_missing = True

        for key in unexpected_keys:
            if key in self.settings:
                self.log.error(f"unexpected key {key} found in settings file.")
                invalid_key = True
                
        if keys_missing or invalid_key:
            self.log.error("Problems verifying Settings file. There are some essential settings missing.")
            raise CrashPlanError("ERROR(Settings.verify(): Problems verifying settings file.")

        else:
            self.settings['settings-dir'] = os.path.join(os.environ['HOME'], self.settings['settings-dir'])
            os.makedirs(self.settings['settings-dir'], mode=0o755, exist_ok=True)

            if self.settings["extra-backup-sources"].find(',') > -1:
                self.settings["extra-backup-sources-list"] = self.settings["extra-backup-sources"].split(',')
            else:
                self.settings["extra-backup-sources-list"] = [self.settings["extra-backup-sources"]]
            
            # check if server name and address match each other
            if self.settings['server-name'] != '':
                try:
                    server_address = socket.gethostbyname(self.settings['server-name'])
                except socket.gaierror as exc:
                    self.log.error(exc)
                    raise CrashPlanError("ERROR(Settings.verify(): server %s not available on network." % self.settings['server-name'])
            else:
                raise CrashPlanError("ERROR(Settings.verify(): server-name is empty.")
                
            if 'server-address' in self.settings and self.settings['server-address'] != "":
                if self.settings['server-address'] != server_address:
                    raise CrashPlanError("ERROR(Settings.verify(): Server name and Address do not match.")
            else:
                self.settings['server-address'] = server_address
        
            self.settings['local-hostname'] = socket.gethostname()
            self.log.info("Settings file verified.")
    
    def set(self, key, val):
        """add a key,val pair to the settings"""
        self.settings[key] = val
        
    def remove(self, key):
        """remove a key from the settings"""
        self.settings.pop(key, None)

    def __call__(self, key):
        """return a value for a given key"""
        if key not in self.settings:
            raise CrashPlanError("Invalid settings attribute - %s" % key)
            
        return self.settings[key]

