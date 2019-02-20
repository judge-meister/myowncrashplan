#!/usr/bin/env python

"""
myowncrashplan.py - backup script

v2.0 - backup run on laptop sending files to server 

Still To Do
===========

- Record current status of backup
- create initial backuo folder on destination
- check backup is not already running
- check we haven't already backup today.
- remove oldest backup to free space - not the last one though
- once finished successfully 
  - update record of date of latest backup
  - update LATEST symlink
  - remove WORKING symlink
- after unsuccessfully backup
  - find latest and create symlink called WORKING

"""

import os
import sys
import stat
import time
import shutil
import getopt
import json
import socket
from glob import glob
from subprocess import getstatusoutput as unix

FORCE = False
DRY_RUN = True
LOGFILE = "myowncrashplan.log"
CONFIG_FILE = "settings.json"

class CrashPlanError(Exception):
    """crash plan error"""
    def __init__(self, value):
        """init"""
        self.value = value
    def __str__(self):
        """str"""
        return repr(self.value)


class TimeDate(object):
    """Date and Time object"""
    def __init__(self):
        pass
        
    def stamp(self):
        return time.strftime("%Y/%m/%d %H:%M:%S")
        
    def datedir(self):
        return time.strftime("%Y-%m-%d-%H%M%S")

class Log(object):
    """Logging object"""
    def __init__(self, logfile):
        self.logfile = logfile
        self.time = TimeDate()

    def __call__(self, msg):
        """write to the log file"""
        if DRY_RUN:
            pass #print("Append to log file - %s" % msg)
        d = self.time.stamp()
        line = "%s [%d] - %s\n" % (d, os.getpid(), msg)
        open(self.logfile, 'a').write(line)


# Potential other options to cater for:
#   backing up to a mounted disk (usb or network)
#     "mount-point": "/Volumes/<something>",
#     "mount-source": "/zdata/myowncrashplan",  or "/dev/usb1",
#     "use-mounted-partition": true,
#
settings_json = """
{
    "server-name": "skynet",
    "server-address": "192.168.0.7",
    "backup-destination": "/zdata/myowncrashplan",
    "backup-destination-uses-hostname": true, 
    "backup-sources-extra": "/Volumes/Nifty128",
    "logfilename": "myowncrashplan.log",
    "rsync-options-exclude": "--delete --delete-excluded ",
    "rsync-exclude-file": "myocp_excl",
    "rsync-options": "--log-file=myowncrashplan.log --quiet --bwlimit=2500 --timeout=300 ",
    "rsync-excludes-hidden": ".AppleDB,.AppleDesktop,.AppleDouble,:2e*,.DS_Store,._*,.Trashes,.Trash,.fseventsd,.bzvol,.cocoapods",
    "rsync-excludes-folders": "lost+found,Network Trash Folder,Temporary Items,Saved Application State,Library,Parallels,VirtualBoxVMs",
    "myocp-debug": true,
    "myocp-tmp-dir": ".myocp",
    "local-mount-point": ".myocp/mnt",
    "reomte-mount-fstype": "smb",
    "remote-mount-user": "judge",
    "remote-mount-pswd": "r0adster",
    "remote-mount-point": "/zdata",
    "remote-mount-backup-dir": "myowncrashplan"
}
"""

class Settings(object):
    """Settings object"""
    def __init__(self, path):
        """"""
        self.path = path
        self.log = Log(LOGFILE)
        self.load()
        self.verify()
        
    def load(self):
        """load settings file """
        try:
            if os.path.exists(self.path):
                self.settings = json.load(open(self.path, 'r'))
            else:
                # use path as a string initially
                self.settings = json.loads(self.path)
            self.log("Settings file loaded.")
        except json.decoder.JSONDecodeError as exc:
            print("ERROR(load_settings()): problems loading settings file (%s)" % exc)
            self.log("ERROR(load_settings()): problems loading settings file (%s)" % exc)
            sys.exit(1)
        else:
            if self.settings['myocp-debug']:
                print("Settings Loaded")
                for k in self.settings:
                    print("settings[%s] : %s" % (k, self.settings[k]))
        
    def verify(self):
        """verify settings are consistent"""
        # check if server name and address match each other
        # merge rsync-excludes-hidden and rsync-excludes-folder lists
        self.settings['rsync-excludes-list'] = self.settings['rsync-excludes-hidden'].split(',')
        self.settings['rsync-excludes-list'] += self.settings['rsync-excludes-folders'].split(',')
        # merge rsync-exclude-file and rsync-exclude-file-option
        self.settings['myocp-tmp-dir'] = os.path.join(os.environ['HOME'], self.settings['myocp-tmp-dir'])
        os.makedirs(self.settings['myocp-tmp-dir'], mode=0o755, exist_ok=True)
        self.settings['rsync-exclude-file'] = os.path.join(self.settings['myocp-tmp-dir'], self.settings['rsync-exclude-file'])
        self.settings['rsync-exclude-file-option'] = "--exclude-from=%s" % (self.settings['rsync-exclude-file'])

        # check if server name and address match each other
        if self.settings['server-address'] != "":
            if self.settings['server-address'] != socket.gethostbyname(self.settings['server-name']):
                raise CrashPlanError("ERROR(Settings.verify(): Server name and Address do not match.")
        else:
            self.settings['server-address'] = socket.gethostbyname(self.settings['server-name'])
        
        self.settings['local-hostname'] = socket.gethostname()
        
        self.log("Settings file verified.")
    
    def create_excl_file(self):
        """create the rsync exclusions file"""
        open(self.settings['rsync-exclude-file'], 'w').write("\n".join(self.settings['rsync-excludes-list']))
        self.log("rsync exclusions file created.")
        if self.settings['myocp-debug']:
            print("create_rsync_excl() - EXCLUDES = \n%s" % self.settings['rsync-excludes-list'])
            print("create_rsync_excl() - %s exists %s" % (self.settings['rsync-exclude-file'], os.path.exists(self.settings['rsync-exclude-file'])))

    def remove_excl_file(self):
        """delete the rsync exclusions file"""
        if os.path.exists(self.settings['rsync-exclude-file']):
            os.unlink(self.settings['rsync-exclude-file'])
            self.log("rsync exclusions file removed.")
        else:
            self.log("rsync exclusions file does not exist.")
            
    def __call__(self, key):
        if key in self.settings:
            return self.settings[key]
        else:
            raise CrashPlanError("Invalid settings attribute - %s" % key)


class RemoteComms(object):
    """Remote Comms object for talking to the remote server"""
    def __init__(self, settings):
        self.settings = settings
        self.log = Log(LOGFILE)
        
    def serverIsUp(self):
        return self.hostIsUp(self.settings('server-address'))
        
    def hostIsUp(self, host_name):
        """is the subject of this backup available"""
        ret = True
        st, _out = unix("ping -q -c1 -W5 %s >/dev/null 2>&1" % host_name)
        if st != 0:
            self.log("Backup subject is Off Line at present.")
            ret = False
        return ret
        
    def remoteCommand(self, command):
        """perform a remote command on the server and get the response"""
        #print(command)
        remote = "ssh -q %s %s" % (self.settings('server-address'), command)
        #print(remote)
        st, rt = unix(remote)
        if st != 0:
            self.log("ERROR(remoteCommand): %s" % command)
            self.log("ERROR(remoteCommand): %d %s" % (st, rt))
            raise CrashPlanError("ERROR: remote command failed. (%s)" % command)
        return rt
    
    def remoteSpace(self):
        """get percentage space used on remote server"""
        response = self.remoteCommand("df -h | grep %s | awk -F' ' '{print $5}'" % self.settings('backup-destination'))
        #print(response)
        return int(response.replace('%',''))
    
    def createRootBackupDir(self):
        """ensure root backup dir exists on remote server"""
        response = self.remoteCommand("mkdir -p %s" % self.settings("backup-destination"))

    def getBackupList(self):
        """"""
        response = self.remoteCommand("ls -d %s/%s/20*" % (self.settings("backup-destination"),self.settings('local-hostname')))
        bu_list = response.split('\n')
        bu_list.sort()
        return bu_list

    def removeOldestBackup(self, oldest):
        """ """
        #response = self.remoteCommand("rm -rf %s" % (oldest))
        print("RemoveOldestBackup(%s)" % oldest)
        
        
class MountCommand(object):
    """create a mount command that is fstype specific
    types - smb, ntfs, nfs, msdos, hfs, exfat 
    smb - currently only one supported
    """
    def __init__(self, settings):
        """"""
        self.local_mount = settings('local-mount-point')
        self.user = settings('remote-mount-user')
        self.pswd = settings('remote-mount-pswd')
        self.server = settings('server-name')
        self.mntpt = settings('remote-mount-point')
        self.fstype = settings('remote-mount-fstype')
        self.tool = ""
        if self.fstype == 'smb':
            self.tool = "mount_smbfs"
        elif self.fstype == "nfs":
            self.tool = "mount_nfs"

    def mount(self):
        """"""
        if self.fstype == "smb":
            # ERROR: mounting using smbfs hides the symlinks, so they cannot be manipulated
            st,rt = unix( _createSmbMountCmd() )
        elif self.fstype == "nfs":
            # ERROR can't seem to mount nfs on my MAc (macos 10.13)
            st,rt = unix( _createNfsMountCmd() )
        return st == 0
        
    def umount(self):
        st,rt = unix( "umount ~/.myocp/mnt")

    def _createSmbMountCmd(self):
        return "%s //%s:%s@%s/%s ~/.myocp/mnt" % (self.tool, self.user, self.pswd, self.server, self.mntpt)

    def _createNfsMountCmd(self):
        return "%s %s:%s ~/.myocp/mnt" % (self.tool, self.server, self.mntpt)


# ------------------------------------------------------------------------------
class CrashPlan(object):
    """control class"""

    def __init__(self, settings, remote_comms, force, dry_run):
        """"""
        self.FORCE = force
        self.DRY_RUN = dry_run
        self.log = Log(LOGFILE)
        # call settings loader and verifier
        self.settings = settings
        self.comms = remote_comms
        self.dt = TimeDate()
        self.DATEDIR = self.dt.datedir()
        self.local_hostname = self.settings('local-hostname')

    def rsync_cmd(self):
        cmd = "rsync -av "
        if self.DRY_RUN:
            cmd += " --dry-run"
        # use LATEST as the link-dest
        cmd += " --link-dest=../LATEST"
        cmd += " "+self.settings('rsync-options-exclude')
        cmd += " "+self.settings('rsync-options')
        cmd += " "+self.settings('rsync-exclude-file-option')
        return cmd
        
    def doBackup(self):
        """
        call rsync for each folder in list of backup sources
        """
        self.settings.create_excl_file()
        sources = [os.environ['HOME']]
        sources += self.settings("backup-sources-extra").split(',')
        try:
            c=0
            for src in sources:
                if self.backupFolder(src):
                    c = c+1
        except KeyboardInterrupt:
            self.log("Backup of %s was interrupted by user intevention" % src)

        self.backupSuccessful = (c == len(sources) and not self.DRY_RUN)
        #self.status.finished()
        #self.settings.remove_excl_file()


    def backupFolder(self, src):
        """
        call - rsync -av --link-dest=../LATEST <src> skynet:/zdata/myowncrashplan/DATEDIR
        
        break this up into 
            1. create cmd, 
            2. do backup, 
            3. classify errors
        """
        cmd = self.rsync_cmd()
        
        # ERROR: this test is acting on the local folder not the remote, so does not work
        if os.path.islink("WORKING"):
            destination = os.path.join(self.settings('backup-destination'), self.local_hostname, "WORKING")
        else:
            destination = os.path.join(self.settings('backup-destination'), self.local_hostname, self.DATEDIR)
            os.symlink(self.DATEDIR, "WORKING")

        cmd += " %s \"%s:%s\" " % (src, self.settings('server-address'), destination)

        self.log("Start Backing Up - %s" % cmd)
        if self.DRY_RUN:
            print("CALL %s" % cmd) 
            st, out = 0, "Done"
        st, out = unix(cmd)

        self.log("doBackup - status = [%d] %s" % (st, out))
        if st == 0:
            # record that a backup has been performed today
            return True #c = c+1
        elif st == 24 or st == 6144 or out.find("some files vanished") > -1: 
            # ignore files vanished warning
            # record that a backup has been performed today
            #c = c+1
            self.log("Backup of %s was successful" % src)
            return True
        else:
            self.log("Backup of %s was not successful" % src)
        return False


    def findOldestBackup(self):
        """"""
        self.backup_list = self.comms.getBackupList()
        return self.backup_list[0]
        
    def prepare(self):
        """"""
        if not self.comms.createRootBackupDir():
            raise CrashPlanError("Error: Cannot create root backup folder.")
            
        oldest = self.findOldestBackup()
        while self.comms.remoteSpace() > 90 and len(self.backup_list) > 1:
            self.comms.removeOldestBackup(oldest)
            oldest = self.findOldestBackup()
        if self.comms.remoteSpace() <= 90:
            self.log("There is enough space.")
            

    def mountedBackupDisk(self):
        """"""
        if mcp.comms.serverIsUp():
            self.mc=MountCommand(self.settings)
            return self.mc.mount()
        return False
            
    def finishUp(self):
        """"""
        if self.mountedBackupDisk():
            if self.backupSuccessful:
                self.updateLatest()
            else:
                self.updateWorking()
            self.mc.umount()
            self.log("myowncrashplan backup attempt completed.")
        else:
            self.log("Cannot finalize the backup")

    def updateLatest(self):
        """update .date file and LATEST symlink"""
        log("Backup was successful. updateLatest()")
        os.chdir("%s" % os.path.join(os.environ['HOME'],settings('local-mount-point'),
                                     self.settings('remote-mount-backup-dir'),
                                     self.settings('local-hostname')))
        open(self.DATEFILE, 'w').write(time.strftime("%d-%m-%Y"))
        
        # rename latest date folder to true latest DATEDIR
        latest = os.path.basename(os.path.realpath('LATEST'))
        shutil.move(os.path.join(self.BACKUPDIR,latest),
                    os.path.join(self.BACKUPDIR,self.DATEDIR))
        
        # create new symlink to latest DATEDIR
        if os.path.islink('LATEST'):
            os.unlink('LATEST')
        else:
            log("ERROR:(updateLatest) LATEST is not a symbolic link.")

        if not os.path.exists('LATEST'):
            log("LATEST backup is now %s" % (self.DATEDIR))
            os.symlink(self.DATEDIR, 'LATEST')

        # remove WORKING if it exists
        if os.path.islink('WORKING'):
            os.unlink('WORKING')
        else:
            log("ERROR:(updateLatest) WORKING is not a symbolic link")
        
    def updateWorking(self):
        """update the WORKING symlink"""
        log("Backup was unsuccessful. updateWorking()")
        os.chdir("%s" % os.path.join(os.environ['HOME'],settings('local-mount-point'),
                                     self.settings('remote-mount-backup-dir'),
                                     self.settings('local-hostname')))

        latest = os.path.basename(os.path.realpath('LATEST'))
        
        if os.path.islink('WORKING'):
            os.unlink('WORKING')
        else:
            log("ERROR:(updateWorking) WORKING is not a symbolic link.")

        if not os.path.exists('WORKING'):
            # create new symlink to latest date dir
            log("WORKING folder is now %s" % (latest))
            os.symlink(latest, 'WORKING')


# ------------------------------------------------------------------------------
# START HERE
#
def get_opts(argv):
    """parse the command line"""
    sopt = 'hnft'
    lopt = ['help', 'dry_run', 'force', 'test']
    
    try:
        opts, args = getopt.getopt(argv, sopt, lopt)
    except getopt.error as cause:
        print("\nError:  failed to parse options (%s)\n" % cause)
        Usage()
        sys.exit(2)
        
    dry_run = force = False

    if opts:
        for o, _a in opts:
            if o in ('-h', '--help'):
                Usage()
                sys.exit()
            if o in ('-n', '--dry_run'):
                dry_run = True
                
            if o in ('-f', '--force'):
                force = True

            if o in ('-t', '--test'):
                # do a test
                mcp = CrashPlan(FORCE, DRY_RUN)
                print(mcp.comms.getBackupList())
                print(mcp.findOldestBackup())
                sys.exit()
    return dry_run, force


def theServerIsUp(comms):
    if comms.serverIsUp():
        print("The Server Is Up")
        return True
    else:
        print("The Server Is Down")
        return False
        
def thereIsEnoughSpace(comms):
    if comms.remoteSpace() < 90:
        print("There is Enough Space")
        return True
    else:
        print("There is Not Enough Space")
        return False

if __name__ == '__main__':
    
    dry_run, force = get_opts(sys.argv[1:])
    
    #test_settings(settings_json)
    settings = Settings(settings_json)
    comms = RemoteComms(settings)

    # can we start - is server on network
    #                have we run a backup today
    #                is it already running
    # prepare - is there enough space
    #           create root backup dir if it doesn't exist
    if theServerIsUp(comms) and thereIsEnoughSpace(comms):
    
        mcp = CrashPlan(settings, comms, force, dry_run)
        mcp.doBackup()
        mcp.finishUp()
    
