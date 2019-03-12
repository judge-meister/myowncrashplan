# pylint: disable=invalid-name
# pylint: disable=trailing-whitespace
# pylint: disable=trailing-newlines

"""
Small utility classes
"""

import time
import subprocess


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


