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
    "backup-sources-extra": "",
    "logfilename": "myowncrashplan.log",
    "rsync-options-exclude": "--delete --delete-excluded ",
    "rsync-exclude-file": "myocp_excl",
    "rsync-options": "--quiet --bwlimit=2500 --timeout=300 ",
    "rsync-excludes-hidden": ".AppleDB,.AppleDesktop,.AppleDouble,:2e*,.DS_Store,._*,.Trashes,.Trash,.fseventsd,.bzvol,.cocoapods",
    "rsync-excludes-folders": "lost+found,Network Trash Folder,Temporary Items,Saved Application State,Library,Parallels,VirtualBoxVMs,VirtualBox VMs",
    "myocp-debug": false,
    "myocp-tmp-dir": ".myocp",
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
            if 'myocp-debug' in self.settings and self.settings['myocp-debug']:
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

    def verify(self):
        """verify settings are consistent"""
        expected_keys = ['rsync-excludes-hidden', 'rsync-excludes-folders', 'myocp-tmp-dir',
                         'backup-sources-extra', 'server-name', 'rsync-exclude-file', 
                         'maximum-used-percent']
        keys_missing = False

        for key in expected_keys:

            if key not in self.settings:
                self.log.error("key %s not found in settings file.")
                keys_missing = True

        if keys_missing:
            self.log.error("Problems verifying Settings file. There are some essential settings missing.")

        else:
            # remove quiet option as it blocks the logging feature
            self.settings['rsync-options'].replace("--quiet", "")

            # merge rsync-excludes-hidden and rsync-excludes-folder lists
            self.settings['rsync-excludes-list'] = self.settings['rsync-excludes-hidden'].split(',')
            self.settings['rsync-excludes-list'] += self.settings['rsync-excludes-folders'].split(',')

            # merge rsync-exclude-file and rsync-exclude-file-option
            self.settings['myocp-tmp-dir'] = os.path.join(os.environ['HOME'], self.settings['myocp-tmp-dir'])
            os.makedirs(self.settings['myocp-tmp-dir'], mode=0o755, exist_ok=True)
            self.settings['rsync-exclude-file'] = os.path.join(self.settings['myocp-tmp-dir'], self.settings['rsync-exclude-file'])
            self.settings['rsync-exclude-file-option'] = "--exclude-from=%s" % (self.settings['rsync-exclude-file'])

            if self.settings["backup-sources-extra"].find(',') > -1:
                self.settings["backup-sources-extra-list"] = self.settings["backup-sources-extra"].split(',')
            else:
                self.settings["backup-sources-extra-list"] = [self.settings["backup-sources-extra"]]
            
            # check if server name and address match each other
            if 'server-address' in self.settings and self.settings['server-address'] != "":
                try:
                    if self.settings['server-address'] != socket.gethostbyname(self.settings['server-name']):
                        raise CrashPlanError("ERROR(Settings.verify(): Server name and Address do not match.")
                except socket.gaierror as exc:
                    self.log(exc)
            else:
                self.settings['server-address'] = socket.gethostbyname(self.settings['server-name'])
        
            self.settings['local-hostname'] = socket.gethostname()
            self.log.info("Settings file verified.")
    
    def create_excl_file(self):
        """create the rsync exclusions file"""
        with open(self.settings['rsync-exclude-file'], 'w') as fp:
            fp.write("\n".join(self.settings['rsync-excludes-list']))

        self.log.info("rsync exclusions file created at %s" % self.settings['rsync-exclude-file'])

        if self.settings['myocp-debug']:
            self.log.debug("create_rsync_excl() - EXCLUDES = \n%s" % self.settings['rsync-excludes-list'])
            self.log.debug("create_rsync_excl() - %s exists %s" % (self.settings['rsync-exclude-file'], 
                                                                   os.path.exists(self.settings['rsync-exclude-file'])))

    def remove_excl_file(self):
        """delete the rsync exclusions file"""
        if 'rsync-exclude-file' in self.settings and os.path.exists(self.settings['rsync-exclude-file']):
            os.unlink(self.settings['rsync-exclude-file'])
            self.log.info("rsync exclusions file removed.")
        else:
            self.log.info("rsync exclusions file does not exist.")
            
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

