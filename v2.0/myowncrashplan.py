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

Ideas
=====
When backup up to a USB drive or filesystem that does not support symbolic
and hard links, then may be try something like a sparsebundle (macos feature) 
as a container. 

For Windows more research is required.

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
from Installation import initialise, install, uninstall
from MetaData import MetaData
from RemoteComms import RemoteComms
from RsyncMethod import RsyncMethod
from Settings import Settings, default_settings_json
from Utils import TimeDate, backupAlreadyRunning#, weHaveBackedUpToday

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
    print("myowncrashplan.py [-h -n -f -t --install --uninstall]")
    print(" -h    this help")
    print(" -n    dry run, do not do an actual backup")
    print(" -f    force even in already run today")
    print(" -t n  run a numbered test")
    print(" --install     install into ~/bin/crashplan")
    print(" --uninstall   uninstall from ~/bin/crashplan")

def get_opts(argv):
    """parse the command line"""
    sopt = 'hnf'
    lopt = ['help', 'dry_run', 'force', 'install', 'uninstall']
    
    try:
        opts, _args = getopt.getopt(argv, sopt, lopt)
    except getopt.error as cause:
        print("\nError:  failed to parse options (%s)\n" % cause)
        Usage()
        sys.exit(2)
        
    options = {'dry_run': False,
               'force': False,
               'install': False,
               'uninstall': False}

    if opts:
        for o, _a in opts:
            if o in ('-h', '--help'):
                Usage()
                sys.exit()

            if o in ('-n', '--dry_run'):
                options['dry_run'] = True
                
            if o in ('-f', '--force'):
                options['force'] = True
                
            if o == '--install':
                options['install'] = True
                
            if o == '--uninstall':
                options['uninstall'] = True

    if options['install'] and options['uninstall']:
        print("ERROR: install and uninstall options are mutually exclusive.")
        sys.exit()
        
    return options

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
    formatter = logging.Formatter(fmt='%(asctime)s [%(process)d] %(levelname)s - %(message)s',
                                  datefmt='%Y/%m/%d %H:%M:%S')
    #formatter = logging.Formatter('%Y/%m/%d %H:%M:%S [%(process)d] %(levelname)s - %(message)s')
    fh.setFormatter(formatter)
    ch.setFormatter(formatter)

    # add the handlers to the logger
    logger.addHandler(fh)
    logger.addHandler(ch)
    
    return logger


def main():
    """do all the preliminary checks before starting a backup"""
    options = get_opts(sys.argv[1:])

    if options['install']:
        install()
        sys.exit()
        
    elif options['uninstall']:
        uninstall()
        sys.exit()

    errlog = createLogger()

    errlog.info("")
    errlog.info("Starting New Backup.")

    initialise(errlog)

    # instantiate some util classes
    settings = Settings(CONFIG_FILE, errlog)
    comms = RemoteComms(settings, errlog)
    meta = MetaData(errlog, comms, settings)
    rsync = RsyncMethod(settings, meta, errlog, comms, options['dry_run'])
    
    if backupAlreadyRunning(errlog):
        sys.exit(0)

    if comms.serverIsUp(): 
        errlog.info("The Server is Up. The backup might be able to start.")
        
        comms.createRootBackupDir()

        if weHaveBackedUpToday(comms, errlog, settings) and not options['force']:
            errlog.info("We Have Already Backed Up Today, so exit here.")
            sys.exit(0)
        elif weHaveBackedUpToday(comms, errlog, settings) and options['force']:
            errlog.info("We Have Already Backed Up Today, but we are running another backup anyway.")
            
        # Is There Enough Space or can space be made available
        #backup_list = comms.getBackupList()
        #oldest = backup_list[0]
        
        #try_anyway = False
        #while comms.remoteSpace() > settings('maximum-used-percent') and len(backup_list) > 1:
        #    comms.removeOldestBackup(oldest)
        #    backup_list = comms.getBackupList()
        #    oldest = backup_list[0]
        #    # temporarily stop here
        #    try_anyway = True
        #    break #sys.exit()

        #try_anyway = True
        #if comms.remoteSpace() <= settings('maximum-used-percent') or try_anyway:
        #    errlog.info("There is enough space for the next backup.")

        mcp = CrashPlan(settings, meta, errlog, comms, rsync, options['dry_run'])
        mcp.doBackup()
        mcp.finishUp()
            


if __name__ == '__main__':
    main()

