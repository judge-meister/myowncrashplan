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

    def today(self):
        return time.strftime("%Y-%m-%d")

class Log(object):
    """Logging object"""
    def __init__(self, logfile):
        self.logfile = logfile
        self.time = TimeDate()

    def __call__(self, msg):
        """write to the log file"""
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
    "remote-mount-fstype": "smb",
    "remote-mount-user": "judge",
    "remote-mount-pswd": "r0adster",
    "remote-mount-point": "/zdata",
    "remote-mount-backup-dir": "myowncrashplan",
    "maximum-used-percent" : 90
}
"""

class MetaData(object):
    """"""
    def __init__(self, json_str=None):
        """"""
        self.expected_keys = ['latest-complete','backup-today']
        if json_str:
            self.meta = json.loads(json_str)
            for k in self.expected_keys:
                if k not in self.meta:
                    raise CrashPlanError("(__init__)metadata does not have all the expected keys.")
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
            #sys.exit(1)
            raise CrashPlanError(exc)
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
        response = self.remoteCommand("df -h | grep %s | awk -F' ' '{print $5}'" % self.settings('backup-destination'))
        #print(response)
        return int(response.replace('%',''))
    
    def createRootBackupDir(self):
        """ensure root backup dir exists on remote server"""
        return self.remoteCommand("mkdir -p %s" % self.settings("backup-destination"))

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
        
    def readMetaData(self):
        """"""
        cmd = "cat %s/.metadata" % os.path.join(self.settings('backup-destination'),self.settings('local-hostname'))
        return self.remoteCommand(cmd)
        
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

    def __init__(self, settings, remote_comms, dry_run):
        """"""
        self.DRY_RUN = dry_run
        self.log = Log(LOGFILE)
        # call settings loader and verifier
        self.settings = settings
        self.comms = remote_comms
        self.dt = TimeDate()
        self.local_hostname = self.settings('local-hostname')
        self.meta = MetaData(self.comms.readMetaData())

    def rsyncCmd(self):
        cmd = "rsync -av "
        if self.DRY_RUN:
            cmd += " --dry-run"
        # use LATEST as the link-dest
        cmd += " --link-dest=../%s" % (self.meta.get('latest-complete'))
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

        result = self.examinationOfResults(st, out)
        self.log("Backup of %s was %ssuccessful\n" % (src, '' if result == True else 'not '))
        return result

    def examinationOfResults(self, st, out):
        """return true if status returned is 0 or a known set of non-zero values"""
        self.log("doBackup - status = [%d] %s" % (st, out))
        if st == 0:
            # record that a backup has been performed today
            return True #c = c+1
        elif st == 24 or st == 6144 or out.find("some files vanished") > -1: 
            # ignore files vanished warning
            # record that a backup has been performed today
            #c = c+1
            #self.log("Backup of %s was successful" % src)
            return True
        #self.log("Backup of %s was not successful\n" % src)
        return False

    def finishUp(self):
        """write .metadata file"""
        if self.backupSuccessful:
            now = self.dt.datedir()
            meta2 = MetaData()
            meta2.set("latest-complete", now)
            meta2.set("backup-today", self.dt.today())
            try:
                self.comms.writeMetaData(repr(meta2))
                src = os.path.join(self.settings('backup-destination'),self.settings('local-hostname'),"WORKING")
                dest = os.path.join(self.settings('backup-destination'),self.settings('local-hostname'),now)
                self.comms.remoteCommand("mv %s %s" % (src, dest))
            except CrashPlanError as exc:
                print(exc)


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
            rt = self.comms.remoteCommand("ls -la %s" % (os.path.join(self.settings('backup-destination'),self.settings('local-hostname'))))
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

def weHaveBackedUpToday(comms):
    """this relies on remote metadata, which could be stored locally also"""
    meta = MetaData(comms.readMetaData())
    dt = TimeDate()
    if meta.get('backup-today') == dt.today:
        return True
    return False

def main():
    """do all the preliminary checks before starting a backup"""
    dry_run, force = get_opts(sys.argv[1:])
    
    # instantiate some util classes
    settings = Settings(settings_json)
    comms = RemoteComms(settings)
    log = Log(LOGFILE)

    # basic tests before we start 
    if backupAlreadyRunning():
        log("Backup already running. [pid %s], so exit here." % (out))
        sys.exit(0)

    # - is the server up? 
    # - have we backed up today?
    if comms.serverIsUp(): 
        log("The Server is Up. The backup might be able to start.")
        
        comms.createRootBackupDir()

        if weHaveBackedUpToday(comms) and not force:
            log("We Have Already Backed Up Today, so exit here.")
            sys.exit(0)
        elif weHaveBackedUpToday(comms) and force:
            log("We Have Already Backed Up Today, but we are running another backup anyway.")
            
        # Is There Enough Space or can space be made available
        backup_list = comms.getBackupList()
        oldest = backup_list[0]
        
        while comms.remoteSpace() > settings('maximum-used-percent') and len(backup_list) > 1:
            comms.removeOldestBackup(oldest)
            backup_list = comms.getBackupList()
            oldest = backup_list[0]

        if comms.remoteSpace() <= settings('maximum-used-percent'):
            log("There is enough space for the next backup.")

            mcp = CrashPlan(settings, comms, dry_run)
            mcp.doBackup()
            mcp.finishUp()
    

if __name__ == '__main__':
    main()

