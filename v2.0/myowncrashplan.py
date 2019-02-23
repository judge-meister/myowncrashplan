#!/usr/bin/env python

"""
MyOwnCrashPlan

myowncrashplan.py - backup script

v2.0 - backup run on laptop sending files to server 

-----------------

Backup Scenarios

* incremental backup successful, after a previous successful backup.
- new <Date/Time> folder created in <Hostname> folder containing latest 
  complete backup. This <Date/Time> folder is referenced in metadata as 
  LATEST_COMPLETE.

* incremental backup failed to complete.
- LATEST_COMPLETE not pointing to true latest <Date/Time> folder. WORKING 
  folder still exists.

* incremental backup starts after a previous failed to complete backup.
- Use WORKING and link to LATEST_COMPLETE to continue the backup. 

* incremental backup completes after starting from incomplete backup.
- Once complete, rename WORKING to <Date/Time NOW> and update LATEST_COMPLETE 
  in metadata.

Store Meta Data

meta data needs to contain;

* date of last backup, for checking if backup done today
* name of LATEST_COMPLETE <Date/Time> folder
	
Notes

We could always use the name WORKING for backups in progress and only rename 
them to Date/Time once complete. That way if WORKING exists the backup will 
use it, if not then it'll get created.  In both cases LATEST_COMPLETE will be
used for linking.

We need to check that the destination filesystem supports hardlinks and 
symlinks, because smbfs mounts do not.  If using a usb drive then it would 
have to be formatted with something that does supported it.

-----------------
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

BACKUPLOG_FILE = os.path.join(os.environ['HOME'],".myocp","backup.log")
ERRORLOG_FILE = os.path.join(os.environ['HOME'],".myocp","error.log")
CONFIG_FILE = os.path.join(os.environ['HOME'],".myocp","settings.json")

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
    
    @staticmethod
    def stamp():
        return time.strftime("%Y/%m/%d %H:%M:%S")
        
    @staticmethod
    def datedir():
        return time.strftime("%Y-%m-%d-%H%M%S")

    @staticmethod
    def today():
        return time.strftime("%Y-%m-%d")

class Log(object):
    """Logging object"""
    def __init__(self, logfile):
        self.logfile = logfile

    def __call__(self, msg):
        """write to the log file"""
        line = "%s [%d] - %s\n" % (TimeDate.stamp(), os.getpid(), msg)
        open(self.logfile, 'a').write(line)


# Potential other options to cater for:
#   backing up to a mounted disk (usb or network)
#     "mount-point": "/Volumes/<something>",
#     "mount-source": "/zdata/myowncrashplan",  or "/dev/usb1",
#     "use-mounted-partition": true,
#
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
    "rsync-options": "--quiet --bwlimit=2500 --timeout=300 ",
    "rsync-excludes-hidden": ".AppleDB,.AppleDesktop,.AppleDouble,:2e*,.DS_Store,._*,.Trashes,.Trash,.fseventsd,.bzvol,.cocoapods",
    "rsync-excludes-folders": "lost+found,Network Trash Folder,Temporary Items,Saved Application State,Library,Parallels,VirtualBoxVMs",
    "myocp-debug": false,
    "myocp-tmp-dir": ".myocp",
    "maximum-used-percent" : 90,
    "local-mount-point": ".myocp/mnt",
    "remote-mount-fstype": "smb",
    "remote-mount-user": "judge",
    "remote-mount-pswd": "r0adster",
    "remote-mount-point": "/zdata",
    "remote-mount-backup-dir": "myowncrashplan"
}
"""

class MetaData(object):
    """"""
    def __init__(self, log, json_str=None):
        """"""
        assert isinstance(log, Log)
        self.log = log
        self.expected_keys = ['latest-complete','backup-today']
        if json_str:
            self.meta = json.loads(json_str)
            for k in self.expected_keys:
                if k not in self.meta:
                    #raise CrashPlanError("(__init__)metadata does not have all the expected keys.")
                    self.log("(__init__)metadata does not have all the expected keys.")
                    self.meta[k] = ""
        else:
            self.meta = {}

    def get(self, key):
        """"""
        if key in self.meta:
            return self.meta[key]
        else:
            raise CrashPlanError("(get) Invalid meta data key - %s" % key)
    
    def set(self, key, val):
        """"""
        if key in self.expected_keys:
            self.meta[key] = val
        else:
            raise CrashPlanError("(set) Invalid meta data key - %s" % key)
            
    def __repr__(self):
        """"""
        return json.dumps(self.meta)+"\n"

class Settings(object):
    """Settings object"""
    def __init__(self, path, log):
        """"""
        assert isinstance(log, Log)
        assert isinstance(path, str)
        self.path = path
        self.log = log
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
            #sys.exit(1)
            raise CrashPlanError(exc)
        else:
            if self.settings['myocp-debug']:
                print("Settings Loaded")
                for k in self.settings:
                    print("settings[%s] : %s" % (k, self.settings[k]))
        
    def write(self, filename):
        """write the settins.json file"""
        if not os.path.exists(os.path.dirname(filename)):
            os.makedirs(os.path.dirname(filename))
        json_str = json.dumps(self.settings, sort_keys=True, indent=4)
        open(filename, "w").write(json_str)

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
        if self.settings["backup-sources-extra"].find(',') > -1:
            self.settings["backup-sources-extra-list"] = self.settings["backup-sources-extra"].split(',')
        else:
            self.settings["backup-sources-extra-list"] = [self.settings["backup-sources-extra"]]
            
        # check if server name and address match each other
        if self.settings['server-address'] != "":
            try:
                if self.settings['server-address'] != socket.gethostbyname(self.settings['server-name']):
                    raise CrashPlanError("ERROR(Settings.verify(): Server name and Address do not match.")
            except socket.gaierror as exc:
                self.log(exc)
        else:
            self.settings['server-address'] = socket.gethostbyname(self.settings['server-name'])
        
        self.settings['local-hostname'] = socket.gethostname()
        
        self.log("Settings file verified.")
    
    def create_excl_file(self):
        """create the rsync exclusions file"""
        open(self.settings['rsync-exclude-file'], 'w').write("\n".join(self.settings['rsync-excludes-list']))
        self.log("rsync exclusions file created at %s" % self.settings['rsync-exclude-file'])
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
            
    def set(self, key, val):
        """"""
        self.settings[key] = val
        
    def remove(self, key):
        """"""
        self.settings.pop(key, None)

    def __call__(self, key):
        if key in self.settings:
            return self.settings[key]
        else:
            raise CrashPlanError("Invalid settings attribute - %s" % key)


class RemoteComms(object):
    """Remote Comms object for talking to the remote server"""
    def __init__(self, settings, log):
        assert isinstance(settings, Settings)
        assert isinstance(log, Log)
        self.settings = settings
        self.log = log
        
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
            #raise CrashPlanError("ERROR: remote command failed. (%s)" % command)
        return st,rt

    def remoteCopy(self, filename):
        """scp file server:/path/to/dir"""
        remote = "scp %s %s:%s" % (filename, self.settings('server-address'), os.path.join(self.settings("backup-destination"),self.settings('local-hostname')))
        st,rt = unix(remote)
        if st != 0:
            self.log("ERROR(remoteCommand): %s" % remote)
            self.log("ERROR(remoteCommand): %d %s" % (st, rt))
            raise CrashPlanError("ERROR: remote command failed. (%s)" % remote)

    def remoteSpace(self):
        """get percentage space used on remote server"""
        st, response = self.remoteCommand("df -h | grep %s | awk -F' ' '{print $5}'" % self.settings('backup-destination'))
        #print(response)
        return int(response.replace('%',''))
    
    def createRootBackupDir(self):
        """ensure root backup dir exists on remote server"""
        st, rt = self.remoteCommand("mkdir -p %s" % os.path.join(self.settings("backup-destination"),self.settings('local-hostname')))
        return rt

    def getBackupList(self):
        """"""
        st, response = self.remoteCommand("ls -d %s/%s/20*" % (self.settings("backup-destination"),self.settings('local-hostname')))
        if st == 0:
            bu_list = response.split('\n')
            bu_list.sort()
            return bu_list
        else:
            return []

    def removeOldestBackup(self, oldest):
        """ """
        #response = self.remoteCommand("rm -rf %s" % (oldest))
        print("RemoveOldestBackup(%s)" % oldest)
        
    def readMetaData(self):
        """"""
        cmd = "cat %s/.metadata" % os.path.join(self.settings('backup-destination'),self.settings('local-hostname'))
        st,rt = self.remoteCommand(cmd)
        if st != 0:
            if rt.find('No such file or') > -1:
                return "{}"
        return rt
        
    def writeMetaData(self, meta):
        """"""
        metafile = os.path.join(os.environ['HOME'],self.settings("myocp-tmp-dir"), '.metadata')
        open(metafile, 'w').write(meta)
        self.remoteCopy(metafile)
        
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
        #elif self.fstype == "nfs":
        #    self.tool = "mount_nfs"

    def mount(self):
        """"""
        if self.fstype == "smb":
            # ERROR: mounting using smbfs hides the symlinks, so they cannot be manipulated
            st,rt = unix( self._createSmbMountCmd() )
        #elif self.fstype == "nfs":
            # ERROR can't seem to mount nfs on my MAc (macos 10.13)
        #    st,rt = unix( self._createNfsMountCmd() )
        return st == 0
        
    def umount(self):
        st,rt = unix( "umount ~/.myocp/mnt")

    def _createSmbMountCmd(self):
        return "%s //%s:%s@%s/%s ~/.myocp/mnt" % (self.tool, self.user, self.pswd, self.server, self.mntpt)

    #def _createNfsMountCmd(self):
    #    return "%s %s:%s ~/.myocp/mnt" % (self.tool, self.server, self.mntpt)


# ------------------------------------------------------------------------------
class CrashPlan(object):
    """control class"""

    def __init__(self, settings, meta, log, remote_comms, dry_run):
        """"""
        assert isinstance(settings, Settings)
        assert isinstance(remote_comms, RemoteComms)
        assert isinstance(meta, MetaData)
        assert isinstance(log, Log)
        self.DRY_RUN = dry_run
        self.log = log
        # call settings loader and verifier
        self.settings = settings
        self.comms = remote_comms
        self.local_hostname = self.settings('local-hostname')
        self.meta = meta 

    def rsyncCmd(self):
        cmd = "rsync -av "
        if self.DRY_RUN:
            cmd += " --dry-run"
        # use LATEST as the link-dest
        if self.meta.get('latest-complete') != "" and os.path.exists(self.meta.get('latest-complete')):
            cmd += " --link-dest=../%s" % (self.meta.get('latest-complete'))
        else:
            baklist = self.comms.getBackupList()
            if len(baklist) > 0:
                cmd += " --link-dest=../%s" % os.path.basename(baklist[-1])
        cmd += " "+self.settings('rsync-options-exclude')
        cmd += " "+self.settings('rsync-options')
        cmd += " --log-file=%s" % BACKUPLOG_FILE #--log-file=myowncrashplan.log
        cmd += " "+self.settings('rsync-exclude-file-option')
        return cmd
        
    def doBackup(self):
        """
        call rsync for each folder in list of backup sources
        """
        self.settings.create_excl_file()
        sources = [os.environ['HOME']]
        for extra in self.settings("backup-sources-extra-list"):
            if extra != '' and os.path.exists(extra):
                sources.append(extra)
        try:
            c=0
            for src in sources:
                if self.backupFolder(src):
                    c = c+1
        except KeyboardInterrupt:
            self.log("Backup of %s was interrupted by user intevention" % src)

        self.backupSuccessful = (c == len(sources) and not self.DRY_RUN)
        print ("Backup successful? ",self.backupSuccessful, "len(sources) = ", len(sources))
        print ("sources: ",sources)
        #self.status.finished()
        self.settings.remove_excl_file()

    def backupFolder(self, src):
        """
        rsync -av --link-dest=../LATEST <src> <server-address>:<backup-destination>/<local-hostname>/WORKING
        """
        cmd = self.rsyncCmd()
        
        destination = os.path.join(self.settings('backup-destination'), self.local_hostname, "WORKING")

        cmd += " %s \"%s:%s\" " % (src, self.settings('server-address'), destination)

        self.log("Start Backing Up to - %s" % destination)
        self.log(cmd)
        
        print("CALL %s" % cmd) 
        st, out = unix(cmd)

        result = self.interpretResults(st, out)
        self.log("Backup of %s was %ssuccessful\n" % (src, '' if result == True else 'not '))
        return result

    def interpretResults(self, st, out):
        """return true if status returned is 0 or a known set of non-zero values"""
        self.log("doBackup - status = [%d] %s" % (st, out))
        if st == 0:
            # record that a backup has been performed today
            return True 
        elif st == 24 or st == 6144 or out.find("some files vanished") > -1: 
            # ignore files vanished warning
            # record that a backup has been performed today
            self.log("Some files vanished (code 24 or 6144) - Filesystem changed after backup started.")
            return True
        elif st == 23: # some files could not be transferred - permission denied at source
            # ignore this error, files probably not owned by current user
            # record that a backup has been performed today
            self.log("Some files could not be transferred (code 23) - look for files/folders you cannot read.")
            return True
        return False

    def finishUp(self):
        """write .metadata file"""
        if self.backupSuccessful:
            meta2 = MetaData(self.log)
            meta2.set("latest-complete", TimeDate.datedir())
            meta2.set("backup-today", TimeDate.today())
            try:
                self.comms.writeMetaData(repr(meta2))
                src = os.path.join(self.settings('backup-destination'), self.settings('local-hostname'), "WORKING")
                dest = os.path.join(self.settings('backup-destination'), self.settings('local-hostname'), TimeDate.datedir())
                self.comms.remoteCommand("mv %s %s" % (src, dest))
            except CrashPlanError as exc:
                print(exc)


# ------------------------------------------------------------------------------
# START HERE
#
def Usage():
    print("myowncrashplan.py [-h -n -f -t]")
    print(" -h    this help")
    print(" -n    dry run, do not do an actual backup")
    print(" -f    force even in already run today")
    print(" -t n  run a numbered test")
    
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
                #test = int(_a)
                t=Testing()
                sys.exit()

    return dry_run, force

def backupAlreadyRunning():
    """is the backup already running"""
    pid = os.getpid()
    pidof = "ps -eo pid,command |awk '{$1=$1};1' | grep 'python /usr/local/bin/myowncrashplan' "
    pidof += "| grep -v grep | cut -d' ' -f1 | grep -v %d" % pid
    _st, out = unix(pidof)
    if out != "":
        return True
    return False

def weHaveBackedUpToday(comms, log):
    """this relies on remote metadata, which could be stored locally also"""
    assert isinstance(comms, RemoteComms)
    assert isinstance(log, Log)
    meta = MetaData(log, comms.readMetaData())
    if meta.get('backup-today') == TimeDate.today():
        return True
    return False

def initialise(errlog):
    """initialise the settings file"""
    # server-name
    # backup-destination
    # backup-sources-extra
    assert isinstance(errlog, Log)
    if not os.path.exists(CONFIG_FILE):
        settings = Settings(default_settings_json, errlog)
        print("Crash Plan settings file missing.")
        yes = "n"
        while yes[0].lower() != "y":
            srvname = input("\nPlease enter the hostname of the backup server/NAS: ")
            try:
                srvaddr = socket.gethostbyname(srvname)
                print(srvaddr)
                yes = "y"
            except socket.gaierror as exc:
                yes = input("This server name does not resolve to an ip address. Are you sure it's correct? [Y/n] ")
        settings.set('server-name', srvname)
        settings.set('server-address', srvaddr)
        backuproot = "."
        while backuproot[0] != "/":
            backuproot = input("\nPlease enter the root directory to use as a backup location. Should start with '/': ")
        settings.set('backup-destination', backuproot)
        settings.remove('rsync-excludes-list')
        settings.remove('backup-sources-extra-list')
        yes = input("\nBy default your home directory will be backed up. Do you have any other location to be backed up? [y/N] ")
        if yes[0].lower() == "y":
            extras = input("Enter any extra locations as a comma seperated list: ")
            settings.set('backup-sources-extra', extras)
        settings.write(CONFIG_FILE)
        print("\nTake a look at ~/.myocp/settings.json to examine the exclusions filters before starting the first backup.")
        sys.exit()

def rotateLog(logfile):
    """"""
    print("rotateLog(%s)" % logfile)
    

def main():
    """do all the preliminary checks before starting a backup"""
    dry_run, force = get_opts(sys.argv[1:])

    baklog = Log(BACKUPLOG_FILE)
    errlog = Log(ERRORLOG_FILE)
    
    initialise(errlog)

    # instantiate some util classes
    settings = Settings(CONFIG_FILE, errlog)
    comms = RemoteComms(settings, errlog)
    meta = MetaData(errlog, comms.readMetaData())
    
    # basic tests before we start 
    if backupAlreadyRunning():
        baklog("Backup already running. [pid %s], so exit here." % (out))
        sys.exit(0)

    # - is the server up? 
    # - have we backed up today?
    if comms.serverIsUp(): 
        baklog("The Server is Up. The backup might be able to start.")
        
        comms.createRootBackupDir()

        if weHaveBackedUpToday(comms, errlog) and not force:
            baklog("We Have Already Backed Up Today, so exit here.")
            sys.exit(0)
        elif weHaveBackedUpToday(comms, errlog) and force:
            baklog("We Have Already Backed Up Today, but we are running another backup anyway.")
            
        # Is There Enough Space or can space be made available
        backup_list = comms.getBackupList()
        oldest = backup_list[0]
        
        while comms.remoteSpace() > settings('maximum-used-percent') and len(backup_list) > 1:
            comms.removeOldestBackup(oldest)
            backup_list = comms.getBackupList()
            oldest = backup_list[0]

        if comms.remoteSpace() <= settings('maximum-used-percent'):
            baklog("There is enough space for the next backup.")

            mcp = CrashPlan(settings, meta, baklog, comms, dry_run)
            mcp.doBackup()
            mcp.finishUp()
            
    rotateLog(BACKUPLOG_FILE)
    rotateLog(ERRORLOG_FILE)
    

if __name__ == '__main__':
    main()

