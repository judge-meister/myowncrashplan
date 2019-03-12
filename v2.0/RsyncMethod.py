# pylint: disable=invalid-name
# pylint: disable=trailing-whitespace
# pylint: disable=trailing-newlines

"""
RsyncMethod


"""

import os
import shlex
import logging
from Settings import Settings
from RemoteComms import RemoteComms
from MetaData import MetaData
from Utils import process


RSYNC = "rsync"
RSYNC_OPTIONS = "--bwlimit=2500 --timeout=300 --delete --delete-excluded "
RSYNC_EXCLUDE_FILE = "myocp_excl"
RSYNC_EXCLUDE_FILE_OPTION = "--exclude_from="

# rsync return codes to deal with
RSYNC_SUCCESS = 0
RSYNC_FILES_VANISHED = 24
RSYNC_FILES_ALSO_VANISHED = 6144
RSYNC_FILES_COULD_NOT_BE_TRANSFERRED = 23

class RsyncMethod():
    """a method of doing backups using rsync"""
    
    def __init__(self, settings, meta, log, comms, dry_run=False):
        """constructor"""
        assert isinstance(settings, Settings)
        assert isinstance(meta, MetaData)
        assert isinstance(log, logging.Logger)
        assert isinstance(comms, RemoteComms)
        
        self.settings = settings
        self.meta = meta
        self.log = log
        self.comms = comms
        self.dry_run = dry_run
        self.cmd = None

        self.exclude_file = os.path.join(os.environ['HOME'], self.settings('settings-dir'), RSYNC_EXCLUDE_FILE)


    def buildCommand(self, src, dest):
        """create the backup command"""
        self.cmd = self._rsyncCmd()
        self.cmd += " %s \"%s:%s\" " % (src, self.settings('server-address'), dest)

    def run(self):
        """run the backup command"""
        self.log.info(self.cmd)
        self._create_exclude_file()
        
        st, rt = process(shlex.split(self.cmd))
        
        self._remove_exclude_file()
        return self._interpretResults(st, rt)


    def _rsyncCmd(self):
        """construct rsync command from settings"""
        cmd = RSYNC + " -av"

        if self.dry_run:
            cmd += " --dry-run"

        #if self.meta.get('latest-complete') != "": 
           #and os.path.exists(self.meta.get('latest-complete')):
        #    cmd += " --link-dest=../%s" % (self.meta.get('latest-complete'))
        #else:
        if self.meta.get('latest-complete') != "": 
            backup_list = self.comms.getBackupList()

            if backup_list:
                cmd += " --link-dest=../%s" % os.path.basename(backup_list[-1])

        #cmd += " "+self.settings('rsync-options-exclude')
        #cmd += " "+self.settings('rsync-options')
        cmd += " "+RSYNC_OPTIONS
        cmd += " --exclude-from="+self.exclude_file

        return cmd


    def _interpretResults(self, status, output):
        """return true if status returned is 0 or a known set of non-zero values"""
        
        self.log.info("do_backup - status = [%d] %s" % (status, output))

        if status == 0:
            # record that a backup has been performed today
            return True 

        if status == RSYNC_FILES_VANISHED or status == RSYNC_FILES_ALSO_VANISHED \
            or output.find("some files vanished") > -1: 
            # ignore files vanished warning
            # record that a backup has been performed today
            # pylint: disable=line-too-long
            self.log.info("Some files vanished (code 24 or 6144) - Filesystem changed after backup started.")
            return True

        if status == RSYNC_FILES_COULD_NOT_BE_TRANSFERRED: 
            # some files could not be transferred - permission denied at source ignore this error,
            # files probably not owned by current user record that a backup has been performed 
            # today.
            # pylint: disable=line-too-long
            self.log.info("Some files could not be transferred (code 23) - look for files/folders you cannot read.")
            return True

        return False

    def _create_exclude_file(self):
        """create the rsync exclusions file"""
        exclude_file_list = self.settings('exclude-files').split(',')
        exclude_file_list += self.settings('exclude-folders').split(',')
        with open(self.exclude_file, 'w') as fp:
            fp.write("\n".join(exclude_file_list))

        self.log.info("rsync exclusions file created at %s" % self.exclude_file)

        if self.settings('debug-level') > 0:
            self.log.debug("_create_exclude_file() - EXCLUDES = \n%s" % excludes_file_list)
            self.log.debug("_create_exclude_file() - %s exists %s" % (self.exclude_file), 
                                                                      os.path.exists(self.exclude_file))

    def _remove_exclude_file(self):
        """delete the rsync exclusions file"""
        if os.path.exists(self.exclude_file):
            os.unlink(self.exclude_file)
            self.log.info("rsync exclusions file removed.")
        else:
            self.log.info("rsync exclusions file does not exist.")


class FakeLog(logging.Logger):
    def __init__(self):
        self.val = {'info':[], 'debug':[], 'error':[]}

    def getVal(self,key):
        return "|".join(self.val[key])

    def info(self, val):
        self.val['info'].append(val)

    def debug(self, val):
        self.val['debug'].append(val)

    def error(self, val):
        self.val['error'].append(val)
        #print(val)


if __name__ == '__main__':
    
    from myowncrashplan import CONFIG_FILE

    # instantiate some util classes
    errlog = FakeLog()
    settings = Settings(CONFIG_FILE, errlog)
    comms = RemoteComms(settings, errlog)
    meta = MetaData(errlog, comms, settings)
    comms = RemoteComms(settings, errlog)
    
    rsync = RsyncMethod(settings, meta, errlog, comms)

    rsync.buildCommand("/Users/judge", "/zdata/myowncrashplan/Prometheus.local/WORKING")
    
    print(rsync.cmd)