#!/usr/bin/env python3

"""
print status of myowncrashplan backup
"""

import sys
import time
import getopt
from subprocess import getstatusoutput as unix

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

def hostisup():
    s, o = unix('ping -c1 -t1 -q skynet 2>/dev/null 1>&2')
    if s != 0:
        return False
    return True


def show_names():
    out="[ Crash Plan Status :\n"
    #print "[ Status :",
    out+="[ Latest Backup :"
    return out


def show_data():
    global Running, Preparing, BackingUp, ServerPresent
    out=""
    
    if not hostisup():
        out+="Unavaiable ]\n"
        out+="Unavaiable ]"
        return out
    
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
        out+="Server Off-line ]\n"
    else:
        if BackingUp:
            out+="Backing Up ]\n"
        elif Preparing:
            out+="Preparing ]\n"
        elif Running:
            out+="Running ]\n"
        else:
            out+="Idle ]\n"

        if latest_time < time.localtime():
            out+="%s ]\n" % (datestr_out)
    return out[:-1]


def myocp_status(opt, args):
    
    for o,a in opt:
        if o == "-h":
            print("myocp_status.py -n -d")
            sys.exit()
            
        if o == "-n": # show names
            print( show_names() )
            sys.exit()
            
        if o == "-d": # show data
            print( show_data() )
            sys.exit()


if __name__ == '__main__':
    
    try:
        opt, args = getopt.getopt(sys.argv[1:], "ndh", ["names","data","help"])
    except getopt.error as v:
        print(v)
        sys.exit()
    
    myocp_status(opt, args)

