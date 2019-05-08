
import os
import sys
import socket
import logging

from Settings import Settings, default_settings_json
from Utils import process

CONFIG_FILE = os.path.join(os.environ['HOME'], ".myocp", "settings.json")

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
        settings.remove('extra-backup-sources-list')
        yes = input("\nBy default your home directory will be backed up. Do you have any other location to be backed up? [y/N] ")

        if yes[0].lower() == "y":
            extras = input("Enter any extra locations as a comma separated list: ")
            settings.set('extra-backup-sources', extras)

        settings.write(CONFIG_FILE)
        print("\nTake a look at ~/.myocp/settings.json to examine the exclude-* filters before starting the first backup.")
        sys.exit()


manifest = ['CrashPlan.py',
            'CrashPlanError.py',
            'MetaData.py',
            'MountCommand.py',
            'RemoteComms.py',
            'RsyncMethod.py',
            'Settings.py',
            'Utils.py',
            'myowncrashplan.py']

def install():
    """install in ~/bin/crashplan"""
    for inst in manifest:
        if not os.path.exists(inst):
            print("Cannot find {0!s}. Are you sure you're in the source folder.".format(ins))
            sys.exit()
    
    inst_dest = os.path.join(os.environ['HOME'],"bin","crashplan")
    os.makedirs(inst_dest)
    for inst in manifest:
        shutil.copy(inst, inst_dest)
    
    # install launchd plist file
    plist = "com.myowncrashplan.plist"
    launchagents = os.path.join(os.environ['HOME'], "Library", "LaunchAgents")
    shutil.copy(plist, launchagents)
    process("launchctl load {0!s}".format(os.path.join(launchagents, plist)))
    

def uninstall():
    """uninstall from ~/bin/crashplan"""
    # uninstall launchd plist file
    plist = "com.myowncrashplan.plist"
    launchagents = os.path.join(os.environ['HOME'], "Library", "LaunchAgents")
    process("launchctl unload {0!s}".format(os.path.join(launchagents, plist)))
    os.unlink(os.path.join(launchagents, plist))
    
    inst_dest = os.path.join(os.environ['HOME'],"bin","crashplan")
    shutil.rmtree(inst_dest)
    