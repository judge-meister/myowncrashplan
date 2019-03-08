# pylint: disable=invalid-name
# pylint: disable=trailing-whitespace
# pylint: disable=trailing-newlines

"""
Store Meta Data

meta data needs to contain;

* date of last backup, for checking if backup done today
* name of LATEST_COMPLETE <Date/Time> folder

"""

import os
import json
import logging
from CrashPlanError import CrashPlanError
from RemoteComms import RemoteComms
from Settings import Settings

class MetaData():
    """MetaData class"""

    def __init__(self, log, comms, settings, json_str=None):
        """initialise the metadata class"""
        assert isinstance(log, logging.Logger)
        assert isinstance(comms, RemoteComms)
        assert isinstance(settings, Settings)

        self.log = log
        self.comms = comms
        self.settings = settings
        self.expected_keys = ['latest-complete', 'backup-today']

        if json_str:
            self.meta = json.loads(json_str)

            for k in self.expected_keys:
                if k not in self.meta:
                    self.log.info("(__init__)metadata does not have all the expected keys.")
                    self.meta[k] = ""
        else:
            self.meta = {}

    def get(self, key):
        """get a value from the metadata"""
        if key not in self.meta:
            raise CrashPlanError("(get) Invalid meta data key - %s" % key)
            
        return self.meta[key]
    
    def set(self, key, val):
        """set a value in the metadata"""
        if key not in self.expected_keys:
            raise CrashPlanError("(set) Invalid meta data key - %s" % key)

        self.meta[key] = val
        
    def __repr__(self):
        """dump the json version of the metadata"""
        return json.dumps(self.meta)+"\n"


    def readMetaData(self):
        """read the remote metadata file"""
        cmd = "cat %s/.metadata" % os.path.join(self.settings('backup-destination'), 
                                                self.settings('local-hostname'))
        st, rt = self.comms.remoteCommand(cmd)

        if st != 0:
            if rt.find('No such file or') > -1:
                return "{}"

        return rt
        
    def writeMetaData(self):
        """write the metadata file locally and copy it to remote server"""
        metafile = os.path.join(os.environ['HOME'], self.settings("myocp-tmp-dir"), '.metadata')

        with open(metafile, 'w') as fp:
            fp.write(repr(self))

        self.comms.remoteCopy(metafile)

