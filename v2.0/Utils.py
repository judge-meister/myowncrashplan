# pylint: disable=invalid-name
# pylint: disable=trailing-whitespace
# pylint: disable=trailing-newlines

"""
Small utility classes
"""

import time
import logging
import subprocess

from RemoteComms import RemoteComms
from Settings import Settings
from MetaData import MetaData


class TimeDate():
    """Date and Time object"""
    
    @staticmethod
    def stamp():
        """return a timestamp"""
        return time.strftime("%Y/%m/%d %H:%M:%S")
        
    @staticmethod
    def datedir():
        """return a datedir name"""
        return time.strftime("%Y-%m-%d-%H%M%S")

    @staticmethod
    def today():
        """return a representing todays date"""
        return time.strftime("%Y-%m-%d")


def process(cmd, log=None):
    """execute a command using Popen and collect the output and return status.
    also there is a option to log an info message if log is defined.
    """
    with subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE) as proc:
        res = []
        while True:
            output = proc.stdout.readline()
            errout = proc.stderr.readline()
        
            if output == b'' and errout == b'' and proc.poll() is not None:
                break

            if output:
                res.append(output.decode().replace('\n', ''))
            if errout:
                res.append(errout.decode().replace('\n', ''))

            if output and log:
                try:
                    log.info(output.strip().decode())
                except UnicodeDecodeError:
                    log.info(output.strip())

    st = proc.poll()
    rt = '\n'.join(res)
    #print(f"(process) rt = {rt}")
    #print(f"(process) st = {st}")
    return st, rt


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


