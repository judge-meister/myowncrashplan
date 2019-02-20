#!/usr/bin/env python

"""
myowncrashplan.py - backup script
"""

import os
import sys
import stat
import time
import shutil
import getopt
import ConfigParser
from glob import glob
from commands import getstatusoutput as unix

RSYNC_OPTS = "--log-file=myowncrashplan.log --quiet --bwlimit=2500 --timeout=300 --delete "
RSYNC_OPTS += "--delete-excluded --exclude-from=rsync_excl"
DRY_RUN = False
DRY_RUN_STR = ""
FORCE = False
HOME = os.environ['HOME']
CONFIGFILE = os.path.join(HOME, ".myowncrashplan.ini")
LOGFILE = "myowncrashplan.log"
MAX_USED_SPACE_PERC=90.0

class CrashPlanError(Exception):
    """crash plan error"""
    def __init__(self, value):
        """init"""
        self.value = value
    def __str__(self):
        """str"""
        return repr(self.value)


def _createFile(name):
    """create a file"""
    _fp = open(name, 'w')
    _fp.close()
    
def _removeFile(name):
    """remove a file"""
    try:
        os.unlink(name)
    except OSError:
        pass

class Status(object):
    """class to control status files"""
    RUNNING = ".running"
    PREPARING = ".preparing"
    BACKINGUP = ".backingup"
    
    def __init__(self, dirname):
        """"""
        self.dirname = dirname
        
    def started(self):
        """create running file"""
        _createFile(os.path.join(self.dirname, self.RUNNING))
        
    def stopped(self):
        """remove running file"""
        _removeFile(os.path.join(self.dirname, self.RUNNING))

    def preparing(self):
        """create preparing file"""
        _createFile(os.path.join(self.dirname, self.PREPARING))

    def finished(self):
        """remove preparing and backingup files"""
        _removeFile(os.path.join(self.dirname, self.PREPARING))
        _removeFile(os.path.join(self.dirname, self.BACKINGUP))

    def backingup(self):
        """create backingup file"""
        _removeFile(os.path.join(self.dirname, self.PREPARING))
        _createFile(os.path.join(self.dirname, self.BACKINGUP))

    def clear(self):
        """remove all status files"""
        _removeFile(os.path.join(self.dirname, self.RUNNING))
        _removeFile(os.path.join(self.dirname, self.PREPARING))
        _removeFile(os.path.join(self.dirname, self.BACKINGUP))


def log(msg):
    """write to the log file"""
    if DRY_RUN:
        print "Append to log file - %s" % msg
    d = time.strftime("%Y/%m/%d %H:%M:%S")
    line = "%s [%d] - %s\n" % (d, os.getpid(), msg)
    open(LOGFILE, 'a').write(line)


def ConfigSectionMap(section):
    """
    return a dict representing the section options
    """
    Config = ConfigParser.ConfigParser()
    Config.read(CONFIGFILE)

    dict1 = {}
    options = Config.options(section)
    for option in options:
        try:
            dict1[option] = Config.get(section, option)
            if dict1[option] == -1:
                pass #DebugPrint("skip: %s" % option)
            
            elif dict1[option].lower() == 'false':
                dict1[option] = False
            elif dict1[option].lower() == 'true':
                dict1[option] = True
            
            else:
                # try converting to integer
                try:
                    dict1[option] = int(dict1[option])
                except ValueError:
                    pass
        except:
            print "exception on %s!" % option
            dict1[option] = None
    return dict1


def createNextBackupFolder(datedir, backupdir):
    """create a new backup folder by using hard links
    
    NOTE: this could be redundant if the right rsync options are used
    """
    try:
        if DRY_RUN:
            print "create new backup folder %s" % datedir
        os.mkdir(datedir)
    except:
        log("Problems creating new backup dir %s" % datedir)
        return False
    
    log("Creating Next Backup Folder %s" % (datedir))
    for root, dirs, files in os.walk('LATEST/', topdown=False, followlinks=False):
        dstpath = os.path.join(backupdir, datedir, root[7:])
        p = ''
        for x in root[7:].split('/'):
            p += x
            if os.path.islink(os.path.join(backupdir, datedir, p)):
                print p, ' is a link'
            else:
                pass #print p,' is a dir'
            p += '/'
        
        if not os.path.exists(dstpath):
            os.makedirs(dstpath)
        
        for name in files:
            src = os.path.join(backupdir, root, name)
            dst = os.path.join(backupdir, datedir, root[7:], name)
            os.link(src, dst)
            if not os.path.islink(src):
                atime = os.stat(src).st_atime
                mtime = os.stat(src).st_mtime
                mode = os.stat(src).st_mode
                os.utime(dst, (atime, mtime))
        
        for name in dirs:
            src = os.path.join(backupdir, root, name)
            atime = os.stat(src).st_atime
            mtime = os.stat(src).st_mtime
            mode = os.stat(src).st_mode
            dst = os.path.join(backupdir, datedir, root[7:], name)
            if not os.path.islink(src):
                try:
                    os.makedirs(dst, mode)
                except OSError:
                    os.chmod(dst, mode)
                os.utime(dst, (atime, mtime))
            else:
                os.link(src, dst)
    return True


def createRootBackupDir(backupdir):
    """check config was loaded and then create the root backup folder"""
    ret = True
    if backupdir == "": 
        print "Need to define BACKUPDIR in config file (~/.myowncrashplan.ini)"
        ret = False 
    
    if not os.path.isdir(backupdir):
        try:
            os.makedirs(backupdir)
        except:
            print "Problems creating", backupdir
            ret = False 
    return ret


def hostIsUp(host_wifi):
    """is the subject of this backup available"""
    ret = True
    st, _out = unix("ping -q -c1 -W5 %s >/dev/null 2>&1" % host_wifi)
    if st != 0:
        log("Backup subject is Off Line at present.")
        ret = False
    return ret


def backupAlreadyRunning(pid):
    """is the backup already running"""
    ret = False
    pidof = "ps -eo pid,command |awk '{$1=$1};1' | grep 'python /usr/local/bin/myowncrashplan' "
    pidof += "| grep -v grep | cut -d' ' -f1 | grep -v %d" % pid
    _st, out = unix(pidof)
    if out != "":
        log("Backup already running. [pid %s]" % (out))
        ret = True
    return ret


def weHaveAlreadyRunBackupToday(datefile, force):
    """have we run the backup today"""
    ret = False
    budate = unix("cat %s" % datefile)[1]
    today = time.strftime("%d-%m-%Y")
    if budate == today:
        log("Backup performed today already.")
        ret = True
    if force:
        log("Backup performed today already, but doing another one anyway.")
        ret = False
    return ret


def fs_size(path):
    """get the file system usage"""
    vfs = os.statvfs(path)

    size = vfs.f_frsize*vfs.f_blocks/1024
    free = vfs.f_frsize*vfs.f_bavail/1024
    used = ((vfs.f_frsize*vfs.f_blocks)-(vfs.f_frsize*vfs.f_bavail))/1024
    return size, free, used


def percent_space(backupdir, datedir):
    """is there enough space"""
    size, _free, used = fs_size(os.path.join(backupdir, datedir))
    return (used*1.0/size*100.0)


def enough_space(backupdir, datedir):
    """is there enough space"""
    return percent_space(backupdir, datedir) < MAX_USED_SPACE_PERC




# ------------------------------------------------------------------------------
# NEW
class CrashPlan(object):
    """control class"""

    def __init__(self, configfile, force, dry_run):
        """ load the preferences """
        self.FORCE = force
        self.DRY_RUN = dry_run
        self.DRY_RUN_STR = "--dry-run"

        self._loadPreferences(configfile)
        self.DATEFILE = os.path.join(self.config['backupdir'], '.date')
        self.BACKUPDIR = self.config['backupdir']
        self.LOGFILE = os.path.join(self.BACKUPDIR, LOGFILE)
        self.HOST_WIFI = self.config['host_wifi']
        self.PID = os.getpid()
        
        os.chdir(self.BACKUPDIR)
        self.status = Status(self.BACKUPDIR)
        self.status.started()
        self.backupSuccessful = False
        self.using_workingdir = False
        
        # create next backup folder
        self.DATEDIR = time.strftime("%Y-%m-%d-%H%M%S")


    def _loadPreferences(self, configfile):
        """load ini file and return configuration"""
        if not os.path.exists(configfile):
            print "Config file (~/.myowncrashplan.ini) not found"
            sys.exit(1) 

        self.config = ConfigSectionMap('myocp')
        if self.DRY_RUN: 
            print self.config

        self.sources = ConfigSectionMap('sources')
        if self.DRY_RUN: 
            print self.sources


    def _remove_oldest_backup(self):
        """do as it says"""
        os.chdir(self.BACKUPDIR)
        backups = glob("201*-*")
        backups.sort()
        log("Removing oldest backup %s to free up more space (%d%%)" % (backups[0],
                                          int(percent_space(self.BACKUPDIR, "LATEST"))))
        self._tidyup(backups[0])


    def _tidyup(self, datedir):
        """remove the unfinished latest datedir"""
        def remove_readonly(func, path, _excinfo):
            """onerror func to fix problems when using rmtree"""
            #log("remove_readonly - %s" % path)
            parent = os.path.dirname(path)
            mode = os.stat(path).st_mode
            os.chmod(parent, mode | stat.S_IRWXU)
            os.chmod(path, mode | stat.S_IRWXU)
            func(path)

        if not self.DRY_RUN:
            shutil.rmtree(datedir, onerror=remove_readonly)

    def _last_remaining_backup(self):
        """ """
        os.chdir(self.BACKUPDIR)
        backups = glob("201*-*")
        if len(backups) == 1:
            return True
        return False


    def canWeStart(self):
        """can we start the backup"""
        if not hostIsUp(self.HOST_WIFI):
            raise CrashPlanError("Host is not available.")

        if backupAlreadyRunning(self.PID):
            raise CrashPlanError("Backup Already Running.")

        if weHaveAlreadyRunBackupToday(self.DATEFILE, self.FORCE):
            raise CrashPlanError("We've already run the Backup today.")
        

    def prepare(self):
        """do prep steps before starting the actual backup"""
        self.status.preparing()
        while not enough_space(self.BACKUPDIR, "LATEST") and not self.DRY_RUN and not self._last_remaining_backup():
            self._remove_oldest_backup()
            
        if not createRootBackupDir(self.BACKUPDIR):
            raise CrashPlanError("Cannot create Root folder.")

        os.chdir(self.BACKUPDIR)
    

    def doBackup(self):
        """do the backup using rsync"""
        os.chdir(self.BACKUPDIR)
        self.status.backingup()
        if not os.path.exists("/zdata/myowncrashplan/.backingup"):
            log("ERROR - %s/.backingup wasn't created" % self.BACKUPDIR)
        c = 0
        try:
            for index in self.sources.keys():
                SRC = self.sources[index]

                if self.DRY_RUN:
                    print "Backing up %s" % SRC
                #rsync -av $DRY_RUN $RSYNC_OPTS "$HOST:$SRC" $DATEDIR
                #rsync -av %s --link-dest=LATEST %s \"%s:%s\" %s" % (self.DRY_RUN_STR, RSYNC_OPTS, 
                #                                                   self.HOST_WIFI, SRC, self.DATEDIR)
                cmd = "rsync -av "
                if self.DRY_RUN:
                    cmd += self.DRY_RUN_STR
                
                # use LATEST as the link-dest
                cmd += " --link-dest=../LATEST %s " % (RSYNC_OPTS)
                    
                if os.path.islink("WORKING"):
                    # use WORKING as the destination
                    destination = "WORKING"
                    self.using_workingdir = True
                else:
                    destination = self.DATEDIR
                    os.symlink(self.DATEDIR, "WORKING")
                    self.using_workingdir = False

                cmd += "\"%s:%s\" %s" % (self.HOST_WIFI, SRC, destination)

                log("Start Backing Up - %s" % cmd)
                if self.DRY_RUN:
                    print "CALL %s" % cmd 
                st, out = unix(cmd)

                log("doBackup - status = [%d] %s" % (st, out))
                if st == 0:
                    # record that a backup has been performed today
                    c = c+1
                elif st == 24 or st == 6144 or out.find("some files vanished") > -1: 
                    # ignore files vanished warning
                    # record that a backup has been performed today
                    c = c+1
                    log("Backup of %s was successful" % SRC)
                else:
                    log("Backup of %s was not successful" % SRC)
                    
        except KeyboardInterrupt: # for testing a failing backup
            log("Backup of %s was interrupted by user intevention" % SRC)

        self.backupSuccessful = (c == len(self.sources) and not self.DRY_RUN)
        self.status.finished()


    def finishUp(self):
        """tidy up after the backup"""
        if self.backupSuccessful:
            self.updateLatest()
        else:
            self.updateWorking()
            
        log("myowncrashplan Backup attempt completed.")
        self.status.stopped()


    def updateLatest(self):
        """update the .date file and LATEST symlink after successful Backup"""
        log("Backup was successful. updateLatest()")
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

        log("LATEST backup is now %s" % (self.DATEDIR))
        os.symlink(self.DATEDIR, 'LATEST')

        # remove WORKING if it exists
        if os.path.islink('WORKING'):
            os.unlink('WORKING')
        else:
            log("ERROR:(updateLatest) WORKING is not a symbolic link")


    def updateWorking(self):
        """update the WORKING symlink after an unsuccessful Backup"""
        log("Backup was unsuccessful. updateWorking()")

        latest = os.path.basename(os.path.realpath('LATEST'))
        
        if os.path.islink('WORKING'):
            os.unlink('WORKING')
        else:
            log("ERROR:(updateWorking) WORKING is not a symbolic link.")

        # create new symlink to latest date dir
        log("WORKING folder is now %s" % (latest))
        os.symlink(latest, 'WORKING')


def Usage():
    """some usage"""
    print "\nUsage:  myowncrashplan.py [-h -n -f]"
    print "  -h   help"
    print "  -n   dry run, no actual backup"
    print "  -f   force a backup event if already run today"
    print
    
# ------------------------------------------------------------------------------
# START HERE
#
def get_opts(argv):
    """parse the command line"""
    global FORCE, DRY_RUN, DRY_RUN_STR

    sopt = 'hnft'
    lopt = ['help', 'dry_run', 'force', 'test']
    
    #print argv
    try:
        opts, args = getopt.getopt(argv, sopt, lopt)
        #print "opts", opts, "args", args
    except getopt.error, cause:
        print "\nError:  failed to parse options (%s)\n" % cause
        Usage()
        sys.exit(2)
        
    #output={}

    if opts:
        for o, _a in opts:
            if o in ('-h', '--help'):
                Usage()
                sys.exit()
            if o in ('-n', '--dry_run'):
                DRY_RUN_STR = "--dry-run"
                DRY_RUN = True
                
            if o in ('-f', '--force'):
                FORCE = True

            if o in ('-t', '--test'):
                # do a test
                mcp = CrashPlan(CONFIGFILE, FORCE, DRY_RUN)
                print "TEST1"
                print "Percent Space of LATEST (symlink to existing folder)", percent_space(mcp.BACKUPDIR, 'LATEST')
                os.system('df -h | grep myowncrashplan')
                print "TEST2"
                print "Percent Space of LATEST2 (non-existing file or folder)", percent_space(mcp.BACKUPDIR, 'LATEST2')
                sys.exit()

if __name__ == '__main__':
    
    get_opts(sys.argv[1:])
    #print DRY_RUN, FORCE

    mycrashplan = CrashPlan(CONFIGFILE, FORCE, DRY_RUN)

    try:
        mycrashplan.canWeStart()
        mycrashplan.prepare()
    except CrashPlanError as exc:
        print "CrashPlanError - ", exc.value
        log("CrashPlanError - %s" %  (exc.value))
        mycrashplan.status.finished()
        mycrashplan.status.stopped()
        sys.exit()

    mycrashplan.doBackup()
    mycrashplan.finishUp()

"""
    
if successful backup
    create LATEST link to newest date folder
    remove WORKING link
    
if unsuccessful backup
    create WORKING link to LATEST folder

PROBLEMS
1. Hard coded year filter of 201* will stop working next year
2. There is a bug that deletes the last remaining backup if it uses >90% of available space
  a. added an untesting extra test for last remaining
  b. need to decide what to do if this situation really occurs

"""

