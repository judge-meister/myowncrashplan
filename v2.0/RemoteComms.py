# pylint: disable=invalid-name
# pylint: disable=missing-docstring
# pylint: disable=trailing-whitespace
# pylint: disable=trailing-newlines

import os
import logging
import platform
from Settings import Settings
from Utils import process
from CrashPlanError import CrashPlanError

def ping(host):
    """
    Returns True if host (str) responds to a ping request.
    Remember that a host may not respond to a ping (ICMP) request even if the host name is valid.
    
    Note: on Windows this function will still return True if you get a Destination Host Unreachable
          error.
    """
    # Option for the number of packets as a function of 
    param = '-n' if platform.system().lower() == 'windows' else '-c'
    # Building the command. Ex: "ping -c 1 google.com"
    command = ['ping', '-q', param, '1', '-W5', host]

    st, _rt = process(command)
    return st == 0


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

        if not ping(host_name):
            self.log.error("Backup subject is Off Line at present.")
            ret = False

        return ret
        

    def remoteCommand(self, command):
        """perform a remote command on the server and get the response"""
        remote = ["ssh", "-q", self.settings('server-address')]
        remote.append(command)

        st, rt = process(remote)
        if st != 0:
            self.log.error(f"(remoteCommand): {command}")
            self.log.error(f"(remoteCommand): {st:d} {rt}")

        return st, rt

    def remoteCopy(self, filename, dest=None):
        """scp file server:/path/to/dir"""
        if dest:
            dest_filename = os.path.basename(dest)
        else:
            dest_filename = os.path.basename(filename)
        remote = ["scp", filename, self.settings('server-address')+":"+ 
                  os.path.join(self.settings("backup-destination"), 
                               self.settings('local-hostname'), dest_filename)]

        st, rt = process(remote)

        if st != 0:
            self.log.error(f"(remoteCommand): {remote}")
            self.log.error(f"(remoteCommand): {st:d} {rt}")
            raise CrashPlanError(f"ERROR: remote command failed. ({remote})")

    def remoteSpace(self):
        """get percentage space used on remote server"""
        cmd = "df -h | grep "+self.settings('backup-destination')+" | awk -F' ' '{print $5}'"
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
        cmd = "ls -d %s/20*" % os.path.join(self.settings("backup-destination"), 
                                            self.settings('local-hostname'))
        st, response = self.remoteCommand(cmd)
        bu_list = []
        if st == 0:
            bu_list = response.split('\n')
            bu_list.sort()

        return bu_list

    def removeOldestBackup(self, oldest):
        """TBD - remove the oldest backup folder"""
        self.log.info("RemoveOldestBackup( %s ) - SIMPLE IMPLEMENTATION - MAY FAIL!" % oldest.split('/')[-1])
        cmd = f"rm -rf {oldest}"
        response = self.remoteCommand("rm -rf %s" % (oldest))
        #self.log.error(response)

