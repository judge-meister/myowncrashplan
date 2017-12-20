#!/usr/bin/env python

import os
import sys
import stat
import time
import shutil
import ConfigParser
from commands import getstatusoutput as unix

RSYNC_OPTS = "--log-file=myowncrashplan.log --quiet --bwlimit=2500 --timeout=300 --delete --delete-excluded --exclude-from=rsync_excl"
DRY_RUN = ""
FORCE = False
HOME = os.environ['HOME']
CONFIGFILE = os.path.join(HOME, ".myowncrashplan.ini")
LOGFILE = "myowncrashplan.log"


def log(str):
    """write to the log file"""
    if DRY_RUN != "":
        print "Append to log file - %s" % str
    d = time.strftime("%Y/%m/%d %H:%M:%S")
    line = "%s [%d] - %s\n" % (d, os.getpid(), str)
    open(LOGFILE,'a').write(line)


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
                
            elif 'false' == dict1[option].lower():
                dict1[option] = False
            elif 'true' == dict1[option].lower():
                dict1[option] = True
                
            else:
                # try converting to integer
                try:
                    dict1[option] = int(dict1[option])
                except ValueError:
                    pass
        except:
            print("exception on %s!" % option)
            dict1[option] = None
    return dict1


def createNextBackupFolder(datedir, backupdir):
    """create a new backup folder by using hard links"""
    try:
        if DRY_RUN != "":
            print "create new backup folder %s" % DATEDIR
        os.mkdir(datedir)
    except:
        log("Problems creating new backup dir %s" % DATEDIR)
        return False
    
    log("Creating Next Backup Folder %s" % (datedir))
    for root, dirs, files in os.walk('LATEST/', topdown=False, followlinks=False):
        dstpath = os.path.join(backupdir, datedir, root[7:])
        p=''
        for x in root[7:].split('/'):
            p=p+x
            if os.path.islink(os.path.join(backupdir, datedir, p)):
                print p,' is a link'
            else:
                pass #print p,' is a dir'
            p=p+'/'
        
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
        ret = False #sys.exit(1)
    
    if not os.path.isdir(backupdir):
        try:
            os.makedirs(backupdir)
        except:
            print "Problems creating", backupdir
            ret = False #sys.exit(1)
    return ret


def hostIsUp(host_wifi):
    """is the subject of this backup available"""
    ret = True
    st, out = unix("ping -q -c1 -W5 %s >/dev/null 2>&1" % host_wifi)
    if st != 0:
        log("Backup subject is Off Line at present.")
        ret = False
    return ret


def backupAlreadyRunning(pid):
    """is the backup already running"""
    ret = False
    pidof = "ps -eo pid,command |awk '{$1=$1};1' | grep 'python /usr/local/bin/myowncrashplan' | grep -v grep | cut -d' ' -f1 | grep -v %d" % pid
    st, out = unix(pidof)
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


def loadPreferences(configfile):
    """load ini file and return configuration"""
    if not os.path.exists(configfile):
        print "Config file (~/.myowncrashplan.ini) not found"
        sys.exit(1) 

    config = ConfigSectionMap('myocp')
    if DRY_RUN != "": print config

    sources = ConfigSectionMap('sources')
    if DRY_RUN != "": print sources

    return config, sources


def doBackup():
    """do the backup using rsync"""
    c = 0
    for index in sources.keys():
        SRC = sources[index]

        if DRY_RUN != "":
            print "Backing up %s" % SRC
        #rsync -av $DRY_RUN $RSYNC_OPTS "$HOST:$SRC" $DATEDIR
        if DRY_RUN != "":
            print "CALL rsync -av %s %s \"%s:%s\" %s" % (DRY_RUN, RSYNC_OPTS, HOST_WIFI, SRC, DATEDIR)
        st, out = unix("rsync -av %s %s \"%s:%s\" %s" % (DRY_RUN, RSYNC_OPTS, HOST_WIFI, SRC, DATEDIR))

        log("doBackup - status = [%d] %s" % (st, out))
        if st == 0:
            # record that a backup has been performed today
            c = c+1
        elif st == 24 or st == 6144 or out.find("some files vanished") > -1: 
            # ignore files vanished warning
            # record that a backup has been performed today
            c = c+1
        else:
            log("Backup of %s was not successful" % SRC)
            
    return (c == len(sources))


def updateLatest(datefile, datedir):
    """update the .date file and LATEST symlink"""
    log("Backup was successful.")
    open(datefile,'w').write(time.strftime("%d-%m-%Y"))

    # create new symlink to latest date dir
    if os.path.exists('LATEST') and os.path.islink('LATEST'):
        os.unlink('LATEST')

    log("LATEST backup is now %s" % (datedir))
    os.symlink(datedir, 'LATEST')


def tidyup(datedir):
    """remove the unfinished latest datedir"""
    def remove_readonly(func, path, excinfo):
        """onerror func to fix problems when using rmtree"""
        log("remove_readonly - %s" % path)
        parent = os.path.dirname(path)
        mode = os.stat(path).st_mode
        os.chmod(parent, mode | stat.S_IRWXU)
        os.chmod(path, mode | stat.S_IRWXU)
        func(path)

    shutil.rmtree(datedir, onerror=remove_readonly)


def fs_size(path):
    """get the file system usage"""
    vfs = os.statvfs(path)

    size = vfs.f_frsize*vfs.f_blocks/1024
    free = vfs.f_frsize*vfs.f_bavail/1024
    used = ((vfs.f_frsize*vfs.f_blocks)-(vfs.f_frsize*vfs.f_bavail))/1024
    return size,free,used


def enough_space(backupdir, datedir):
    """"""
    size,free,used = fs_size(os.path.join(backupdir, datedir))
    return (used*1.0/size*100.0) < 90.0


def remove_oldest_backup(backupdir):
    """"""
    from glob import glob
    os.chdir(backupdir)
    backups = glob("201*-*")
    backups.sort()
    log("Removing oldest backup %s to free up more space" % (backups[0]))
    tidyup(backups[0])



# ------------------------------------------------------------------------------
# START HERE
#
if len(sys.argv) > 1 and sys.argv[1] == "-n": 
    DRY_RUN="--dry-run"
if len(sys.argv) > 1 and sys.argv[1] == "-f": 
    FORCE = True

# load preferences
config, sources = loadPreferences(CONFIGFILE)

DATEFILE = os.path.join(config['backupdir'],'.date')
BACKUPDIR = config['backupdir']
LOGFILE = os.path.join(BACKUPDIR, LOGFILE)
HOST_WIFI = config['host_wifi']
PID=os.getpid()

# create next backup folder
DATEDIR = time.strftime("%Y-%m-%d-%H%M%S")

while not enough_space(BACKUPDIR, "LATEST"):
    remove_old_backup(BACKUPDIR)

if not createRootBackupDir(BACKUPDIR):
    sys.exit(1)

os.chdir(BACKUPDIR)

if not hostIsUp(HOST_WIFI):
    sys.exit(1)

if backupAlreadyRunning(PID):
    sys.exit(1)

if weHaveAlreadyRunBackupToday(DATEFILE, FORCE):
    sys.exit(1)
    
# assume source laptop is online as we got here
os.chdir(BACKUPDIR)

if not createNextBackupFolder(DATEDIR, BACKUPDIR):
    sys.exit(1)

# do the actual backup
if doBackup():
    updateLatest(DATEFILE, DATEDIR)
else:
    log("Removing unfinished backup %s" % (DATEDIR))
    tidyup(DATEDIR)

log("myowncrashplan Backup attempt completed.")

