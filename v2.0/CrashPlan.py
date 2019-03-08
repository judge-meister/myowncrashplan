# pylint: disable=invalid-name
# pylint: disable=trailing-whitespace
# pylint: disable=trailing-newlines

"""
Backup Scenarios

* incremental backup successful, after a previous successful backup.
- new <Date/Time> folder created in <Hostname> folder containing latest 
  complete backup. This <Date/Time> folder is referenced in metadata as 
  LATEST_COMPLETE.

* incremental backup failed to complete.
- LATEST_COMPLETE not pointing to true latest <Date/Time> folder. WORKING 
  folder still exists.

* incremental backup starts after a previous failed to complete backup.
- Use WORKING and link to LATEST_COMPLETE to continue the backup.

* incremental backup completes after starting from incomplete backup.
- Once complete, rename WORKING to <Date/Time NOW> and update LATEST_COMPLETE 
  in metadata.

NOTE: We can achieve the above by;
Always use the name WORKING for backups in progress and only rename 
them to Date/Time once complete. That way if WORKING exists the backup will 
use it, if not then it'll get created.  In both cases LATEST_COMPLETE will be
used for linking.

"""

import os
import shlex
import logging
import subprocess
from Settings import Settings
from RemoteComms import RemoteComms
from MetaData import MetaData
from Utils import TimeDate
from CrashPlanError import CrashPlanError

RSYNC_SUCCESS = 0
RSYNC_FILES_VANISHED = 24
RSYNC_FILES_ALSO_VANISHED = 6144
RSYNC_FILES_COULD_NOT_BE_TRANSFERRED = 23


class CrashPlan():
    """control class"""

    # pylint: disable=too-many-arguments
    def __init__(self, settings, meta, log, remote_comms, dry_run):
        """"""
        assert isinstance(settings, Settings)
        assert isinstance(remote_comms, RemoteComms)
        assert isinstance(meta, MetaData)
        assert isinstance(log, logging.Logger)

        self.dry_run = dry_run
        self.log = log
        self.settings = settings
        self.comms = remote_comms
        self.local_hostname = self.settings('local-hostname')
        self.meta = meta 
        self.backup_successful = False

    def rsyncCmd(self):
        """construct rsync command from settings"""
        cmd = "rsync -av"

        if self.dry_run:
            cmd += " --dry-run"

        if self.meta.get('latest-complete') != "" \
           and os.path.exists(self.meta.get('latest-complete')):
            cmd += " --link-dest=../%s" % (self.meta.get('latest-complete'))
        else:
            backup_list = self.comms.getBackupList()

            if backup_list:
                cmd += " --link-dest=../%s" % os.path.basename(backup_list[-1])

        cmd += " "+self.settings('rsync-options-exclude')
        cmd += " "+self.settings('rsync-options')
        cmd += " "+self.settings('rsync-exclude-file-option')

        return cmd
        
    def doBackup(self):
        """
        call rsync for each folder in list of backup sources
        """
        self.settings.create_excl_file()
        sources = [os.environ['HOME']]

        for extra in self.settings("backup-sources-extra-list"):

            if extra != '' and os.path.exists(extra):
                sources.append(extra)

        try:
            count = 0

            for src in sources:
                if self.backupFolder(src):
                    count += 1

        except KeyboardInterrupt:
            self.log.info("Backup of %s was interrupted by user intevention" % src)

        self.backup_successful = (count == len(sources) and not self.dry_run)
        print("Backup successful? ", self.backup_successful, "len(sources) = ", len(sources))
        print("sources: ", sources)
        self.settings.remove_excl_file()

    def backupFolder(self, src):
        """
        NOTE: We always use the name WORKING for backups in progress and only rename 
        them to Date/Time once complete. That way if WORKING exists the backup will 
        use it, if not then it'll get created.  In both cases LATEST_COMPLETE will be
        used for linking.
        
        rsync -av --link-dest=../LATEST <src> 
                 <server-address>:<backup-destination>/<local-hostname>/WORKING
        """
        destination = os.path.join(self.settings('backup-destination'), 
                                   self.local_hostname, "WORKING")

        cmd = self.rsyncCmd()
        cmd += " %s \"%s:%s\" " % (src, self.settings('server-address'), destination)

        self.log.info("Start Backing Up to - %s" % destination)
        self.log.info(cmd)
        
        process = subprocess.Popen(shlex.split(cmd), stdout=subprocess.PIPE)#, shell=True)

        while True:
            output = process.stdout.readline()

            if output == b'' and process.poll() is not None:
                break

            if output:
                try:
                    self.log.info(output.strip().decode())
                except UnicodeDecodeError:
                    self.log.info(output.strip())

        res = process.poll()
        result = self.interpretResults(res, "")
        self.log.info("Backup of %s was %ssuccessful\n" % (src, '' if result else 'not '))

        return result

    def interpretResults(self, status, output):
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

    def finishUp(self):
        """write .metadata file"""
        if self.backup_successful:
            meta2 = MetaData(self.log, self.comms, self.settings)
            meta2.set("latest-complete", TimeDate.datedir())
            meta2.set("backup-today", TimeDate.today())

            try:
                meta2.writeMetaData()
                src = os.path.join(self.settings('backup-destination'), 
                                   self.settings('local-hostname'), "WORKING")
                dest = os.path.join(self.settings('backup-destination'), 
                                    self.settings('local-hostname'), TimeDate.datedir())
                self.comms.remoteCommand("mv %s %s" % (src, dest))
            except CrashPlanError as exc:
                print(exc)
                self.log.error(exc)


