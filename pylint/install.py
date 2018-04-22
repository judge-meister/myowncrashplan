#!/usr/bin/env python

"""
Install

script to install myowncrashplan
"""

import os
import sys
from commands import getstatusoutput as unix
# installation script for myowncrashplan
#
# 1. ask installer for location of backup dir
# 2. move main script to $USER/bin/
# 3. create ~/.mocprc (.myowncrashplanrc)
# 4. install /etc/logrotate.d/myowncrashplan
# 5. install cron job
# 6. create rsync_excl
#

# pylint: disable=too-many-branches
# pylint: disable=too-many-statements
# pylint: disable=too-many-locals
def install():
    """install steps"""

    print "\nThis is the installer for myowncrashplan (version 0.2).\n"

    # 1. ask installer for location of backup dir
    print "Where should we store the backups ? A new folder will be added to the "
    print "specified location. Remember to consider how much space is required to "
    print "backup the target machine. Full path is required."
    finished = False
    while not finished:
        tgtdir = raw_input("[/opt]: ")
        if tgtdir == "":
            tgtdir = "/opt"
        #print "[%s]" % tgtdir
        if not os.path.exists(tgtdir):
            print "INFO: Folder %s does not exist." % tgtdir
            ask = raw_input("Do you want to create this folder. [y/n]: ")
            if ask == 'y' or ask == 'Y':
                finished = True
        else:
            finished = True
    if tgtdir.endswith('/'):
        tgtdir = tgtdir[:-1]
    if not DRYRUN:
        ret, out = unix("mkdir -p %s" % os.path.join(tgtdir, 'myowncrashplan'))


    # 2 ask for ipaddress of target machine
    finished = False
    while not finished:
        ipaddress = raw_input("\nEnter IP Address of target machine. It must be online. [10.0.0.1]: ")
        if ipaddress == "":
            ipaddress = "10.0.0.1"
        ret, out = unix('ping -c 1 -W 3 -q %s > /dev/null' % ipaddress)
        #print s,o
        if ret == 0:
            finished = True
        else:
            print "ERROR: ping test failed. Try again."


    # 3 ask for absolute folders on target to be backed up
    finished = False
    src = []
    print "\nEnter locations on target machine to be backed up. Enter empty string to end."
    print "Use absolute paths."
    while not finished:
        path = raw_input("\nEnter a location: ")
        if path != "":
            if path.endswith('/'):
                path = path[:-1]
            src.append(path)
        else:
            finished = True

    count = 1
    formatted_src = ""
    for idx in src:
        formatted_src += "%d: %s\n" % (count, idx)
        count += 1
    #formatted_src = '"'+'"\n         "'.join(src)+'"\n         '

    print "\nWe need to install files in /usr/local/bin /etc/logrotate.d so we "
    print "need to get superuser access.\n"
    ans = ""
    while ans not in ['y', 'n', 'Y', 'N']:
        ans = raw_input("Do you have sudo configured? (Yes or No) [Yn] : ")

    if ans.lower() == 'y':
        sudo_cmd = 'sudo'
    else:
        sudo_cmd = 'su -c'

    # 4. move main script to /usr/local/bin/
    script_bin = "/usr/local/bin"
    #script_bin = "/home/judge/bin"
    if os.path.exists(script_bin):
        if not DRYRUN:
            ret, out = unix('%s cp -f myowncrashplan.py %s' % (sudo_cmd, script_bin))
            # set permissions of file
            if ret != 0:
                print out
                print "ERROR: Could not copy file to %s" % script_bin
                sys.exit()
    else:
        print "ERROR: %s does not exist" % script_bin
        sys.exit()


    # 5. create ~/.myowncrashplanrc)
    rcfile = """
# .myowncrashplan.ini

[myocp]
# HOST_WIFI is the IP Address of the machine to be backed up
host_wifi: %s

# BACKUPDIR is the absolute location on the server to store the backups
backupdir: %s/myowncrashplan

# SOURCES is a list of locations on the laptop to be backed up
# should be absolute paths and each must NOT end in /
[sources]
%s

""" % (ipaddress, tgtdir, formatted_src)

    print "Created %s/.myowncrashplan.ini" % os.environ['HOME']
    if DRYRUN:
        print "-----------------------------------------\n%s-----------------------------------------" % rcfile
    else:
        open(os.path.join(os.environ['HOME'], '.myowncrashplan.ini'), 'w').write(rcfile)


    # 6. install /etc/logrotate.d/myowncrashplan
    logrot = """
%s/myowncrashplan/myowncrashplan.log {
            size 50M
            copytruncate
            missingok
            rotate 8
            compress
            delaycompress
            notifempty
            create 640 %s %s
}
""" % (tgtdir, os.environ['USER'], os.environ['USER'])

    print "Created /etc/logrotate.d/myowncrashplan"
    if DRYRUN:
        print "-----------------------------------------\n%s-----------------------------------------" % logrot
    else:
        open('/tmp/myowncrashplan', 'w').write(logrot)
        if os.path.exists("/etc/logrotate.d"):
            if not DRYRUN:
                unix("%s cp /tmp/myowncrashplan /etc/logrotate.d/myowncrashplan" % (sudo_cmd))
        else:
            print "ERROR: /etc/logrotate.d does not exist. May be logrotate has not been installed."
            print "       The output log file will not be rotated and will continue to grow."


    # 7. create rsync_excl
    excl = """
lost+found
.AppleDB
.AppleDesktop
.AppleDouble
Network Trash Folder
Temporary Items
:2e*
.DS_Store
._*
.Trashes
.fseventsd
.bzvol
Saved Application State
Library/Caches/Google/Chrome
"""

    print "Created %s" % (os.path.join(tgtdir, 'myowncrashplan', 'rsync_excl'))
    if DRYRUN:
        print "-----------------------------------------\n%s-----------------------------------------" % excl
    else:
        open(os.path.join(tgtdir, 'myowncrashplan', 'rsync_excl'), 'w').write(excl)


    # 8. install cron job
    #print "[still need to create cron job]\n"

    cronjob = "*/60 * * * * %s/myowncrashplan.py" % script_bin
    ret, out = unix("crontab -l 2>/dev/null")
    if ret == 0:
        if out.find('myowncrashplan.py') != -1 or out.find('myowncrashplan.sh') != -1:
            print "\nWARNING: Looks like a previous myowncrashplan cronjob exists."
            print "         Use crontab -e to remove or edit the job.\n"
        if out.find(cronjob) == -1:
            if not DRYRUN:
                ret, out = unix('(crontab -l 2>/dev/null; echo "%s") | crontab -' % cronjob)
                if ret == 0:
                    print "Created a cron job to run the backup."
                else:
                    print "ERROR: Problems creating cron job."
            else:
                print "Adding new job to crontab file."
                print cronjob

    #
    #  */60 * * * * /home/judge/bin/myowncrashplan.py
    #  (crontab -l 2>/dev/null; echo "*/60 * * * * /home/judge/bin/myowncrashplan.py") | crontab -
    #

DRYRUN = False
if len(sys.argv) > 1:
    if sys.argv[1] == "-n":
        DRYRUN = True

if DRYRUN:
    print "DRYRUN", DRYRUN

install()
