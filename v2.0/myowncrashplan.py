#!/usr/bin/env python

# pylint: disable=invalid-name
# pylint: disable=missing-docstring
# pylint: disable=trailing-whitespace
# pylint: disable=trailing-newlines
# pylint: disable=line-too-long
# pylint: disable=wrong-import-position

"""
MyOwnCrashPlan

myowncrashplan.py - backup script

v2.0 - backup run on laptop sending files to server 

Still To Do
===========

- Record current status of running backup
- remove oldest backup to free space - not the last one though
- We need to check that the destination filesystem supports hardlinks and 
symlinks, because smbfs mounts do not.  If using a usb drive then it would 
have to be formatted with something that does supported it.

"""

import sys
import platform

# confirm we are running the right version of python
major, minor, patch = platform.python_version().split('.')
version = float(major)+float(minor)/10.0

if version < 3.5:
    sys.stderr.write("Requires Python >= 3.7\n")
    sys.exit(1)


import os
import getopt
import socket
import logging
import logging.handlers
from subprocess import getstatusoutput as unix

from CrashPlan import CrashPlan
from RemoteComms import RemoteComms
from Settings import Settings, default_settings_json
from MetaData import MetaData
from Utils import TimeDate

BACKUPLOG_FILE = os.path.join(os.environ['HOME'], ".myocp", "backup.log")
ERRORLOG_FILE = os.path.join(os.environ['HOME'], ".myocp", "error.log")
CONFIG_FILE = os.path.join(os.environ['HOME'], ".myocp", "settings.json")



# Potential other options to cater for:
#   backing up to a mounted disk (usb or network)
#     "mount-point": "/Volumes/<something>",
#     "mount-source": "/zdata/myowncrashplan",  or "/dev/usb1",
#     "use-mounted-partition": true,
#



# ------------------------------------------------------------------------------
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
    sopt = 'hnf'
    lopt = ['help', 'dry_run', 'force']
    
    try:
        opts, _args = getopt.getopt(argv, sopt, lopt)
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

    return dry_run, force


def backupAlreadyRunning(errlog):
    """is the backup already running?
     - this works for MacOs and Linux
    """
    pid = os.getpid()
    pidof = "ps -eo pid,command | grep -i 'python .*myowncrashplan' "
    pidof += "| grep -v grep | awk -F' ' '{print $1}' | grep -v '^%d$'" % pid
    _st, out = unix(pidof)

    if out != "":
        errlog.info("Backup already running. [pid %s], so exit here." % (out))
        return True

    return False


def weHaveBackedUpToday(comms, log, settings):
    """this relies on remote metadata, which could be stored locally also"""
    assert isinstance(comms, RemoteComms)
    assert isinstance(log, logging.Logger)
    assert isinstance(settings, Settings)

    meta = MetaData(log, comms, settings)
    meta.readMetaData()
    
    if meta.get('backup-today') == TimeDate.today():
        return True
    return False


def initialise(errlog):
    """initialise the settings file"""
    # server-name
    # backup-destination
    # backup-sources-extra
    assert isinstance(errlog, logging.Logger)

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
            except socket.gaierror:
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


def createLogger():
    """create a logger"""
    # create logger with 'myowncrashplan'
    logger = logging.getLogger('myowncrashplan')
    logger.setLevel(logging.DEBUG)

    # create rotating file handler which logs even debug messages
    fh = logging.handlers.RotatingFileHandler(ERRORLOG_FILE, maxBytes=1024*1024, backupCount=5)
    fh.setLevel(logging.DEBUG)

    # create console handler with a higher log level
    ch = logging.StreamHandler()
    ch.setLevel(logging.ERROR)

    # create formatter and add it to the handlers
    formatter = logging.Formatter('%(asctime)s [%(process)d] %(levelname)s - %(message)s')
    fh.setFormatter(formatter)
    ch.setFormatter(formatter)

    # add the handlers to the logger
    logger.addHandler(fh)
    logger.addHandler(ch)
    
    return logger



def main():
    """do all the preliminary checks before starting a backup"""
    dry_run, force = get_opts(sys.argv[1:])

    errlog = createLogger()

    initialise(errlog)

    # instantiate some util classes
    settings = Settings(CONFIG_FILE, errlog)
    comms = RemoteComms(settings, errlog)
    meta = MetaData(errlog, comms, settings)
    
    if backupAlreadyRunning(errlog):
        sys.exit(0)

    if comms.serverIsUp(): 
        errlog.info("The Server is Up. The backup might be able to start.")
        
        comms.createRootBackupDir()

        if weHaveBackedUpToday(comms, errlog, settings) and not force:
            errlog.info("We Have Already Backed Up Today, so exit here.")
            sys.exit(0)
        elif weHaveBackedUpToday(comms, errlog, settings) and force:
            errlog.info("We Have Already Backed Up Today, but we are running another backup anyway.")
            
        # Is There Enough Space or can space be made available
        backup_list = comms.getBackupList()
        oldest = backup_list[0]
        
        while comms.remoteSpace() > settings('maximum-used-percent') and len(backup_list) > 1:
            comms.removeOldestBackup(oldest)
            backup_list = comms.getBackupList()
            oldest = backup_list[0]

        if comms.remoteSpace() <= settings('maximum-used-percent'):
            errlog.info("There is enough space for the next backup.")

            mcp = CrashPlan(settings, meta, errlog, comms, dry_run)
            mcp.doBackup()
            mcp.finishUp()
            


if __name__ == '__main__':
    main()

