# pylint: disable=invalid-name
# pylint: disable=missing-docstring
# pylint: disable=trailing-whitespace
# pylint: disable=trailing-newlines

import os
import logging
from subprocess import getstatusoutput as unix
from Settings import Settings
from CrashPlanError import CrashPlanError

class RemoteComms():
    """Remote Comms object for talking to the remote server
     - this presumes the server is a Linux box
    """

    def __init__(self, settings, log):
        assert isinstance(settings, Settings)
        assert isinstance(log, logging.Logger)

        self.settings = settings
        self.log = log
        
    def serverIsUp(self):
        """is the server up"""
        return self.hostIsUp(self.settings('server-address'))
        
    def hostIsUp(self, host_name):
        """is the subject of this backup available"""
        ret = True
        st, _out = unix(f"ping -q -c1 -W5 {host_name} >/dev/null 2>&1")

        if st != 0:
            self.log.error("Backup subject is Off Line at present.")
            ret = False

        return ret
        
    def remoteCommand(self, command):
        """perform a remote command on the server and get the response"""
        remote = f"ssh -q {self.settings('server-address')} {command}"
        st, rt = unix(remote)

        if st != 0:
            self.log.error(f"(remoteCommand): {command}")
            self.log.error(f"(remoteCommand): {st:d} {rt}")

        return st, rt

    def remoteCopy(self, filename):
        """scp file server:/path/to/dir"""
        remote = "scp {0:s} {1:s}:{2:s}".format(filename, self.settings('server-address'), 
                                                os.path.join(self.settings("backup-destination"), 
                                                             self.settings('local-hostname')))
        st, rt = unix(remote)

        if st != 0:
            self.log.error(f"(remoteCommand): {remote}")
            self.log.error(f"(remoteCommand): {st:d} {rt}")
            raise CrashPlanError("ERROR: remote command failed. ({remote})")

    def remoteSpace(self):
        """get percentage space used on remote server"""
        cmd = "df -h | grep %s | awk -F' ' '{print $5}'" % self.settings('backup-destination')
        _st, response = self.remoteCommand(cmd)
        return int(response.replace('%', ''))
    
    def createRootBackupDir(self):
        """ensure root backup dir exists on remote server"""
        cmd = "mkdir -p %s" % os.path.join(self.settings("backup-destination"),
                                           self.settings('local-hostname'))
        _st, rt = self.remoteCommand(cmd)
        return rt

    def getBackupList(self):
        """get list of backup folders"""
        cmd = "ls -d %s/%s/20*" % (self.settings("backup-destination"),
                                   self.settings('local-hostname'))
        st, response = self.remoteCommand(cmd)
        bu_list = []
        if st == 0:
            bu_list = response.split('\n')
            bu_list.sort()

        return bu_list

    def removeOldestBackup(self, oldest):
        """TBD - remove the oldest backup folder"""
        self.log.info("RemoveOldestBackup(%s)" % oldest)
        #cmd = f"rm -rf {oldest}"
        #response = self.remoteCommand("rm -rf %s" % (oldest))
        


