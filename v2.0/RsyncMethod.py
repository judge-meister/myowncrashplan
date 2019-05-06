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
from CrashPlan import CrashPlanErrorCodes

BACKUPLOG_FILE = os.path.join(os.environ['HOME'], ".myocp", "backup.log")

RSYNC = "/opt/local/bin/rsync"
RSYNC_OPTIONS = "--bwlimit=2500 --timeout=300 --delete --delete-excluded "
RSYNC_EXCLUDE_FILE = "myocp_excl"
RSYNC_EXCLUDE_FILE_OPTION = "--exclude_from="

# rsync return codes to deal with
RSYNC_SUCCESS = 0
RSYNC_FILES_VANISHED = 24
RSYNC_FILES_ALSO_VANISHED = 6144
RSYNC_FILES_COULD_NOT_BE_TRANSFERRED = 23
RSYNC_TIMEOUT_IN_DATA_SEND_RECIEVE = 30

# reasons
#RSYNC_DISK_FULL = -1
#RSYNC_UNKNOWN_ERROR = -99

class BaseMethod():
    def __init__(self):
        pass

    def buildCommand(self, src, dest):
        """setup command and return nothing"""
        pass

    def run(self):
        """return one of the CrashPlanErrorCodes values"""
        pass

class RsyncMethod(BaseMethod):
    """a method of doing backups using rsync"""

    def __init__(self, settings, meta, log, comms, dry_run=False, getsize=False):
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
        self.getsize = getsize
        self.cmd = None
        self.rsync_log_file = BACKUPLOG_FILE #self.settings('settings-dir') + "/rsync.log"

        self.exclude_file = os.path.join(os.environ['HOME'], self.settings('settings-dir'),
                                         RSYNC_EXCLUDE_FILE)


    def buildCommand(self, src, dest):
        """create the backup command"""
        self.cmd = self._rsyncCmd()
        self.cmd += " %s \"%s:%s\" " % (src, self.settings('server-address'), dest)

    def buildSizeCommand(self, src, dest):
        """create the backup command"""
        self.cmd = self._rsyncSizeCmd()
        self.cmd += " %s \"%s:%s\" " % (src, self.settings('server-address'), dest)

    def run(self):
        """run the backup command"""
        self._create_exclude_file()
        self.log.info(self.cmd)

        st, rt = process(shlex.split(self.cmd))
        if self.dry_run:
            self._calculate_size(rt)
            #print("DRY_RUN",st,rt)

        self._remove_exclude_file()
        return self._interpretResults(st, rt)

    def run2(self):
        """run the backup command"""
        self._create_exclude_file()
        self.log.info(self.cmd)

        st, rt = process(shlex.split(self.cmd))
        self._calculate_size(rt)

        self._remove_exclude_file()

    def _calculate_size(self, rt):
        """when used in dry_run mode we can calculate the space required to do
        the backup
        """
        size_bytes = 0
        for line in return_str.split('\n'):
            if line.startswith('sent '):
                bytestr = line.split(' ')[1]
                try:
                    size += int(bytestr)
                except ValueError:
                    pass
        self.size_required = size/1024

    def _rsyncCmd(self):
        """construct rsync command from settings"""
        cmd = RSYNC + " -av"
        if not self.dry_run:
            cmd += " --log-file=%s" % self.rsync_log_file

        if self.dry_run:
            cmd += " --dry-run"

        if self.meta.get('latest-complete') != "":
            backup_list = self.comms.getBackupList()

            if backup_list:
                cmd += " --link-dest=../%s" % os.path.basename(backup_list[-1])

        cmd += " "+RSYNC_OPTIONS
        cmd += " --exclude-from="+self.exclude_file

        return cmd


    def _rsyncSizeCmd(self):
        """construct rsync command from settings so we can get the required
        backup size.
        """
        cmd = RSYNC + " -av"
        cmd += " --dry-run"
        cmd += " --log-file=%s" % self.rsync_log_file

        if self.meta.get('latest-complete') != "":
            backup_list = self.comms.getBackupList()

            if backup_list:
                cmd += " --link-dest=../%s" % os.path.basename(backup_list[-1])

        cmd += " "+RSYNC_OPTIONS
        cmd += " --exclude-from="+self.exclude_file

        return cmd


    def _interpretResults(self, status, output):
        """return true if status returned is 0 or a known set of non-zero values"""
        success = CrashPlanErrorCodes.SUCCESS

        #self.log.info("do_backup - status = [%d] %s" % (status, output))
        self.log.info("do_backup - status = [%d]" % (status))

        if status == 0:
            # record that a backup has been performed today
            success = CrashPlanErrorCodes.SUCCESS

        elif status == RSYNC_FILES_VANISHED or status == RSYNC_FILES_ALSO_VANISHED \
            or output.find("some files vanished") > -1:
            # ignore files vanished warning
            # record that a backup has been performed today
            # pylint: disable=line-too-long
            self.log.info("Some files vanished (code 24 or 6144) - Filesystem changed after backup started.")
            success = CrashPlanErrorCodes.SUCCESS

        elif status == RSYNC_FILES_COULD_NOT_BE_TRANSFERRED:
            # some files could not be transferred - permission denied at source ignore this error,
            # files probably not owned by current user record that a backup has been performed
            # today.
            # pylint: disable=line-too-long
            self.log.info("Some files could not be transferred (code 23) - look for files/folders you cannot read.")
            success = CrashPlanErrorCodes.SUCCESS

        elif status == RSYNC_TIMEOUT_IN_DATA_SEND_RECIEVE:
            # this could either mean the destination disk is full or that the network connection
            # was really sloe to respond.
            # pylint: disable=line-too-long
            self.log.info("Timeout in data send/recieve (code 30) - Destination disk is probably full.")
            success = CrashPlanErrorCodes.DISK_FULL

        else:
            # rsync returned a status not previously handled so log it and return False
            self.log.info(f"rsync returned '{output}' (code {status})")
            success = CrashPlanErrorCodes.UNKNOWN_ERROR

        return (success)

    def _create_exclude_file(self):
        """create the rsync exclusions file"""
        exclude_file_list = self.settings('exclude-files').split(',')
        exclude_file_list += self.settings('exclude-folders').split(',')
        with open(self.exclude_file, 'w') as fp:
            fp.write("\n".join(exclude_file_list))

        #self.log.info("rsync exclusions file created at %s" % self.exclude_file)

        if self.settings('debug-level') > 0:
            # pylint: disable=line-too-long
            self.log.debug("_create_exclude_file() - EXCLUDES = \n%s" % exclude_file_list)
            self.log.debug("_create_exclude_file() - %s exists %s" % (self.exclude_file,
                                                                      os.path.exists(self.exclude_file)))

    def _remove_exclude_file(self):
        """delete the rsync exclusions file"""
        if os.path.exists(self.exclude_file):
            os.unlink(self.exclude_file)
            #self.log.info("rsync exclusions file removed.")
        else:
            self.log.info("rsync exclusions file does not exist.")
