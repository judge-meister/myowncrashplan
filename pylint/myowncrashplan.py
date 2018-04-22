#!/usr/bin/env python

"""
myowncrashplan.py

This script will run from a cron job and backup the machine configured"
"""

import os
import sys
import stat
import time
import shutil
import ConfigParser
from commands import getstatusoutput as unix

RSYNC_OPTS = "--log-file=myowncrashplan.log --quiet --bwlimit=2500 --timeout=300 --delete "
RSYNC_OPTS += "--delete-excluded --exclude-from=rsync_excl"
DRY_RUN = ""
FORCE = False
HOME = os.environ['HOME']
CONFIGFILE = os.path.join(HOME, ".myowncrashplan.ini")
LOGFILE = "myowncrashplan.log"


def log(msg):
    """write to the log file"""
    if DRY_RUN != "":
        print "Append to log file - %s" % msg
    time_str = time.strftime("%Y/%m/%d %H:%M:%S")
    line = "%s [%d] - %s\n" % (time_str, os.getpid(), msg)
    open(LOGFILE, 'a').write(line)


def config_section_map(section):
    """
    return a dict representing the section options
    """
    myocp_config = ConfigParser.ConfigParser()
    myocp_config.read(CONFIGFILE)

    dict1 = {}
    options = myocp_config.options(section)
    for option in options:
        try:
            dict1[option] = myocp_config.get(section, option)
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
        except: # pylint: disable=bare-except
            print "exception on %s!" % option
            dict1[option] = None
    return dict1


def create_next_backup_folder(datedir, backupdir): # pylint: disable=too-many-branches
    """create a new backup folder by using hard links"""
    try:
        if DRY_RUN != "":
            print "create new backup folder %s" % DATEDIR
        os.mkdir(datedir)
    except OSError:
        log("Problems creating new backup dir %s" % DATEDIR)
        return False

    log("Creating Next Backup Folder %s" % (datedir))
    for root, dirs, files in os.walk('LATEST/', topdown=False, followlinks=False):
        dstpath = os.path.join(backupdir, datedir, root[7:])
        path = ''
        for part in root[7:].split('/'):
            path = path+part
            if os.path.islink(os.path.join(backupdir, datedir, path)):
                print path, ' is a link'
            else:
                pass #print p,' is a dir'
            path = path+'/'

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


def create_root_backup_dir(backupdir):
    """check config was loaded and then create the root backup folder"""
    ret = True
    if backupdir == "":
        print "Need to define BACKUPDIR in config file (~/.myowncrashplan.ini)"
        ret = False #sys.exit(1)

    if not os.path.isdir(backupdir):
        try:
            os.makedirs(backupdir)
        except OSError:
            print "Problems creating", backupdir
            ret = False #sys.exit(1)
    return ret


def host_is_up(host_wifi):
    """is the subject of this backup available"""
    ret = True
    status, _out = unix("ping -q -c1 -W5 %s >/dev/null 2>&1" % host_wifi)
    if status != 0:
        log("Backup subject is Off Line at present.")
        ret = False
    return ret


def backup_already_running(pid):
    """is the backup already running"""
    ret = False
    pidof = "ps -eo pid,command |awk '{$1=$1};1' | grep 'python /usr/local/bin/myowncrashplan' "
    pidof += "| grep -v grep | cut -d' ' -f1 | grep -v %d" % pid
    _status, out = unix(pidof)
    if out != "":
        log("Backup already running. [pid %s]" % (out))
        ret = True
    return ret


def we_already_ran_backup_today(datefile, force):
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


def load_preferences(configfile):
    """load ini file and return configuration"""
    if not os.path.exists(configfile):
        print "Config file (~/.myowncrashplan.ini) not found"
        sys.exit(1)

    cfg = config_section_map('myocp')
    if DRY_RUN != "":
        print cfg

    src = config_section_map('sources')
    if DRY_RUN != "":
        print src

    return cfg, src


def do_backup():
    """do the backup using rsync"""
    count = 0
    for index in SOURCES.keys():
        src = SOURCES[index]

        if DRY_RUN != "":
            print "Backing up %s" % src
        #rsync -av $DRY_RUN $RSYNC_OPTS "$HOST:$SRC" $DATEDIR
        if DRY_RUN != "":
            print "CALL rsync -av %s %s \"%s:%s\" %s" % (DRY_RUN, RSYNC_OPTS, HOST_WIFI, src, DATEDIR)
        status, out = unix("rsync -av %s %s \"%s:%s\" %s" % (DRY_RUN, RSYNC_OPTS, HOST_WIFI, src, DATEDIR))

        log("do_backup - status = [%d] %s" % (status, out))
        if status == 0:
            # record that a backup has been performed today
            count = count+1
        elif status == 24 or status == 6144 or out.find("some files vanished") > -1:
            # ignore files vanished warning
            # record that a backup has been performed today
            count = count+1
        else:
            log("Backup of %s was not successful" % src)

    return count == len(SOURCES)


def update_latest(datefile, datedir):
    """update the .date file and LATEST symlink"""
    log("Backup was successful.")
    open(datefile, 'w').write(time.strftime("%d-%m-%Y"))

    # create new symlink to latest date dir
    if os.path.exists('LATEST') and os.path.islink('LATEST'):
        os.unlink('LATEST')

    log("LATEST backup is now %s" % (datedir))
    os.symlink(datedir, 'LATEST')


def tidyup(datedir):
    """remove the unfinished latest datedir"""
    def remove_readonly(func, path, _excinfo):
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
    #free = vfs.f_frsize*vfs.f_bavail/1024
    used = ((vfs.f_frsize*vfs.f_blocks)-(vfs.f_frsize*vfs.f_bavail))/1024
    return size, used


def enough_space(backupdir, datedir):
    """is there enough space"""
    size, used = fs_size(os.path.join(backupdir, datedir))
    return (used*1.0/size*100.0) < 95.0


def remove_oldest_backup(backupdir):
    """remove the oldest backups"""
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
    DRY_RUN = "--dry-run"
if len(sys.argv) > 1 and sys.argv[1] == "-f":
    FORCE = True

# load preferences
CONFIG, SOURCES = load_preferences(CONFIGFILE)

DATEFILE = os.path.join(CONFIG['backupdir'], '.date')
BACKUPDIR = CONFIG['backupdir']
LOGFILE = os.path.join(BACKUPDIR, LOGFILE)
HOST_WIFI = CONFIG['host_wifi']
PID = os.getpid()

# create next backup folder
DATEDIR = time.strftime("%Y-%m-%d-%H%M%S")

while not enough_space(BACKUPDIR, "LATEST"):
    remove_oldest_backup(BACKUPDIR)

if not create_root_backup_dir(BACKUPDIR):
    sys.exit(1)

os.chdir(BACKUPDIR)

if not host_is_up(HOST_WIFI):
    sys.exit(1)

if backup_already_running(PID):
    sys.exit(1)

if we_already_ran_backup_today(DATEFILE, FORCE):
    sys.exit(1)

# assume source laptop is online as we got here
os.chdir(BACKUPDIR)

if not create_next_backup_folder(DATEDIR, BACKUPDIR):
    sys.exit(1)

# do the actual backup
if do_backup():
    update_latest(DATEFILE, DATEDIR)
else:
    log("Removing unfinished backup %s" % (DATEDIR))
    tidyup(DATEDIR)

log("myowncrashplan Backup attempt completed.")

