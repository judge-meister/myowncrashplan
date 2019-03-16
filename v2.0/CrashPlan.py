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
import logging
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
    def __init__(self, settings, meta, log, remote_comms, method, dry_run):
        """"""
        assert isinstance(settings, Settings)
        assert isinstance(remote_comms, RemoteComms)
        assert isinstance(meta, MetaData)
        assert isinstance(log, logging.Logger)

        self.method = method
        self.dry_run = dry_run
        self.log = log
        self.settings = settings
        self.comms = remote_comms
        self.local_hostname = self.settings('local-hostname')
        self.meta = meta 
        self.backup_successful = False

    def doBackup(self):
        """
        call rsync for each folder in list of backup sources
        """
        #self.settings.create_excl_file()
        sources = [os.environ['HOME']]

        for extra in self.settings("extra-backup-sources-list"):

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
        #self.settings.remove_excl_file()

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

        self.method.buildCommand(src, destination)

        self.log.info("Start Backing Up to - %s" % destination)
        
        result = self.method.run()

        self.log.info("Backup of %s was %ssuccessful\n" % (src, '' if result else 'not '))

        return result

    def finishUp(self):
        """write .metadata file"""
        if self.backup_successful:
            meta2 = MetaData(self.log, self.comms, self.settings, "")
            meta2.set("latest-complete", TimeDate.datedir())
            meta2.set("backup-today", TimeDate.today())

            try:
                meta2.writeMetaData()
                
                # move WORKING to Latest Complete Date
                src = os.path.join(self.settings('backup-destination'), 
                                   self.settings('local-hostname'), "WORKING")
                dest = os.path.join(self.settings('backup-destination'), 
                                    self.settings('local-hostname'), TimeDate.datedir())
                self.comms.remoteCommand(f"mv {src} {dest}")
            except CrashPlanError as exc:
                print(exc)
                self.log.error(exc)


