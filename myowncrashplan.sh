#!/bin/bash
#
# run crontab -e and add the following
#  */60 * * * * /path/to/location/of/myowncrashplan.sh
#

# create file /etc/logrotate.d/myowncrashplan containing the following to rotate log file
#  /zdata/myowncrashplan/myowncrashplan.log {
#        size 50M
#        copytruncate
#        missingok
#        rotate 8
#        compress
#        delaycompress
#        notifempty
#        create 640 judge judge
#  }


RSYNC_OPTS="--log-file=myowncrashplan.log --quiet --bwlimit=5000 --timeout=300 --delete-excluded --exclude-from=rsync_excl"

DRY_RUN=""
if [ "$1" == "-n" ]; then DRY_RUN="--dry-run"; fi

# load preferences
if [ -f  ~/.myowncrashplanrc ]; 
then 
  . ~/.myowncrashplanrc ; 
else 
  echo "Config file (~/.myowncrashplanrc) not found"; exit 1; 
fi
#if [ -f    .myowncrashplanrc ]; then . .myowncrashplanrc ; fi

LOGFILE=$BACKUPDIR/myowncrashplan.log

function log()
{
  d=$(date +"%Y/%m/%d %H:%M:%S")
  echo $d" ["$$"] - "$1 >> $LOGFILE
}

# check preference

if [ "$BACKUPDIR" == "" ]; then echo "Need to define BACKUPDIR in config file (~/.myowncrashplanrc)"; exit 1; fi
if [ ! -d $BACKUPDIR ]; then 
  mkdir -p $BACKUPDIR 
  if [ $? -ne 0 ]; then
    echo "Problems creating "$BACKUPDIR"."
    exit 1
  fi
fi
cd $BACKUPDIR

# is the subject of this backup available
ping -q -c1 -W5 $HOST_WIFI >/dev/null 2>&1
if [ $? -eq 0 ]
then
  HOST=$HOST_WIFI
else
  log "Backup subject is Off Line at present."
  exit 1
fi

# is the backup already running
if [ "$(pidof rsync)" != "" ]; then log "Backup already running."; exit 1; fi

# have we run the backup today
if [ "$(cat $DATEFILE)" == "$(date +%d-%m-%Y)" ]; then log "Backup performed today already."; exit 1; fi

# assume Prometheus is online as we got here
cd $BACKUPDIR

# count the list of SOURCES
count=0
while [ "x${SOURCES[count]}" != "x" ]
do
  count=$(( $count + 1 ))
done

c=0
for index in $(seq 0 $((count-1)) )  
do
  SRC=${SOURCES[index]}
  SRC=${SRC// /\\ }
  rsync -av $DRY_RUN $RSYNC_OPTS "$HOST:$SRC" .
  if [ $? -eq 0 ]
  then
    # record that a backup has been performed today
    c=$((c+1))
  fi
done

if [ $c -eq $count ]
then
  log "Backup was successful."
  date +%d-%m-%Y > $DATEFILE
fi

