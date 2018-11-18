#!/usr/bin/env python

"""
print status of myowncrashplan backup
"""

import sys
import time
import getopt
from commands import getstatusoutput as unix

cmds = {
    "running" : "ssh skynet 2>/dev/null ls /zdata/myowncrashplan/.running",
    "backingup" : "ssh skynet 2>/dev/null ls /zdata/myowncrashplan/.backingup",
    "preparing" : "ssh skynet 2>/dev/null ls /zdata/myowncrashplan/.preparing",
    "latest" : "ssh skynet 2>/dev/null ls -l /zdata/myowncrashplan/LATEST"
}

Running = False
Preparing = False
BackingUp = False
ServerPresent = False

try:
    opt, args = getopt.getopt(sys.argv[1:], "nd", ["names","dryrun"])
except getopt.error, v:
    print v
    sys.exit()
    
for o,a in opt:
    if o == "-n": # show names
        print "[ Crash Plan Status :"
        #print "[ Status :",
        print "[ Latest Backup :"
        sys.exit()
    if o == "-d": # show data

        if unix(cmds["running"])[0] == 0:
            Running = True
    
        if unix(cmds["backingup"])[0] == 0:
            BackingUp = True
            
        if unix(cmds["preparing"])[0] == 0:
            Preparing = True
    
        status, output = unix(cmds["latest"])
        #print status, output
        if status == 0:
            ServerPresent = True

        if ServerPresent:
            datestr_in = output[output.find('->')+3:]

            latest_time = time.strptime(datestr_in, "%Y-%m-%d-%H%M%S")
            #print "Latest Backup - %s" % datestr
            datestr_out = time.strftime("%d/%m/%y",latest_time)

        if not ServerPresent:
            print "Server Off-line ]"
        else:
            if BackingUp:
                print "Backing Up ]"
            elif Preparing:
                print "Preparing ]"
            elif Running:
                print "Running ]"
            else:
                print "Idle ]"
    
            if latest_time < time.localtime():
                print "%s ]" % (datestr_out)
        sys.exit()
