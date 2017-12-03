#!/usr/bin/env python

import os, sys
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
DRYRUN=False
if len(sys.argv) > 1:
    if sys.argv[1] == "-n":
        DRYRUN=True

if DRYRUN:
    print "DRYRUN", DRYRUN

print "\nThis is the installer for myowncrashplan (version 0.1).\n"


# 1. ask installer for location of backup dir
print "Where should we store the backups ? A new folder will be added to the "
print "specified location. Remember to consider how much space is required to "
print "backup the target machine. Full path is required."
FINISHED=False
while not FINISHED:
    TGTDIR = raw_input("[/opt]: ")
    if TGTDIR == "":
        TGTDIR = "/opt"
    #print "[%s]" % TGTDIR
    if not os.path.exists(TGTDIR):
        print "INFO: Folder %s does not exist." % TGTDIR
        ask = raw_input("Do you want to create this folder. [y/n]: ")
        if ask == 'y' or ask == 'Y':
            FINISHED=True
    else:
        FINISHED=True
if TGTDIR.endswith('/'):
    TGTDIR=TGTDIR[:-1]
if not DRYRUN:
    s,o = unix("mkdir -p %s" % os.path.join(TGTDIR,'myowncrashplan'))


# 2 ask for IPADDRESS of target machine
FINISHED=False
while not FINISHED:
    IPADDRESS = raw_input("\nEnter IP Address of target machine. It must be online. [10.0.0.1]: ")
    if IPADDRESS == "":
        IPADDRESS = "10.0.0.1"
    s,o=unix('ping -c 1 -W 3 -q %s > /dev/null' % IPADDRESS)
    #print s,o
    if s == 0:
        FINISHED=True
    else:
        print "ERROR: ping test failed. Try again."
    

# 3 ask for absolute folders on target to be backed up
FINISHED=False
SRC=[]
print "\nEnter locations on target machine to be backed up. Enter empty string to end."
print "Use absolute paths."
while not FINISHED:
    path = raw_input("\nEnter a location: ")
    if path != "":
        if path.endswith('/'):
            path=path[:-1]
        SRC.append(path)
    else:
        FINISHED=True

FORMATTED_SRC = '"'+'"\n         "'.join(SRC)+'"\n         '

print "\nWe need to install files in /usr/local/bin /etc/logrotate.d so we "
print "need to use sudo and ask for your password.\n"


# 4. move main script to /usr/local/bin/ 
SCRIPT_BIN="/usr/local/bin"
#SCRIPT_BIN="/home/judge/bin"
if os.path.exists(SCRIPT_BIN): 
    if not DRYRUN:
        s,o=unix('sudo cp -f myowncrashplan.sh %s' % SCRIPT_BIN)
        # set permissions of file
        if s != 0:
            print o
            print "ERROR: Could not copy file to %s" % SCRIPT_BIN
            sys.exit()
else:
    print "ERROR: %s does not exist" % SCRIPT_BIN
    sys.exit()


# 5. create ~/.myowncrashplanrc)
rc="""
# .myowncrashplanrc

# HOST_WIFI is the IP Address of the machine to be backed up
HOST_WIFI=%s

# BACKUPDIR is the absolute location on the server to store the backups
BACKUPDIR=%s/myowncrashplan

# SOURCES is a list of locations on the laptop to be backed up
# should be absolute paths and each must NOT end in /
SOURCES=(%s)

# file to store date of last backup
DATEFILE=${BACKUPDIR}/.date

""" % (IPADDRESS, TGTDIR, FORMATTED_SRC)

print "Created %s/.myowncrashplanrc" % os.environ['HOME']
if DRYRUN:
    print "-----------------------------------------\n%s-----------------------------------------" % rc
else:
    open(os.path.join(os.environ['HOME'],'.myowncrashplanrc'),'w').write(rc)


# 6. install /etc/logrotate.d/myowncrashplan
lr="""
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
""" % (TGTDIR, os.environ['USER'], os.environ['USER'])
print "Created /etc/logrotate.d/myowncrashplan"
if DRYRUN:
    print "-----------------------------------------\n%s-----------------------------------------" % lr
else:
    open('/tmp/myowncrashplan','w').write(lr)
    if os.path.exists("/etc/logrotate.d"):
        if not DRYRUN:
            unix("sudo cp /tmp/myowncrashplan /etc/logrotate.d/myowncrashplan")
    else:
        print "ERROR: /etc/logrotate.d does not exist. May be logrotate has not been installed."
        print "       The output log file will not be rotated and will continue to grow."
    

# 7. create rsync_excl
excl="""
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
print "Created %s" % (os.path.join(TGTDIR,'myowncrashplan','rsync_excl'))
if DRYRUN:
    print "-----------------------------------------\n%s-----------------------------------------" % excl
else:
    open(os.path.join(TGTDIR,'myowncrashplan','rsync_excl'),'w').write(excl)


# 8. install cron job
#print "[still need to create cron job]\n"

cronjob="*/60 * * * * %s/myowncrashplan.sh" % SCRIPT_BIN
s,o = unix("crontab -l 2>/dev/null")
if s == 0:
    if o.find('myowncrashplan.sh') != -1:
        print "\nWARNING: Looks like a previous myowncrashplan cronjob exists."
        print "         Use crontab -e to remove or edit the job.\n"
    if o.find(cronjob) == -1:
        if not DRYRUN:
            s,o = unix('(crontab -l 2>/dev/null; echo "%s") | crontab -' % cronjob)
            if s == 0:
                print "Created a cron job to run the backup."
            else:
                print "ERROR: Problems creating cron job."
        else:
            print "Adding new job to crontab file."
            print cronjob

"""
*/60 * * * * /home/judge/bin/myowncrashplan.sh
(crontab -l 2>/dev/null; echo "*/60 * * * * /home/judge/bin/myowncrashplan.sh") | crontab -
"""
