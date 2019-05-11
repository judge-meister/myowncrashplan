#!/bin/bash

# /opt/local/bin/rsync -av --dry-run --log-file=/Users/judge/.myocp/backup.log
#     --link-dest=../2019-04-21-200903 --bwlimit=2500 --timeout=300 --delete
#     --delete-excluded --exclude-from=/Users/judge/.myocp/myocp_excl
#     /Users/judge 192.168.0.7:/zdata/myowncrashplan/Prometheus.local/WORKING
#     | grep '^sent' | cut -d' ' -f2

DEBUG=1

server_host=192.168.0.7
local_host=$(hostname)
backup_destination=/zdata/myowncrashplan
log_file=/Users/judge/.myocp/backup.log
exclude_file=/Users/judge/.myocp/myocp_excl
src_folders="/Users/judge"
previous_backup=
RSYNC_CMD="/opt/local/bin/rsync -av --bwlimit=2500 --timeout=300 --delete --delete-excluded "

RSYNC_SUCCESS=0
RSYNC_FILES_VANISHED=24
RSYNC_FILES_ALSO_VANISHED=6144
RSYNC_FILES_COULD_NOT_BE_TRANSFERRED=23
RSYNC_TIMEOUT_IN_DATA_SEND_RECIEVE=30

function space_available()
{
  echo $(ssh ${server_host} df | grep ${backup_destination} | awk -F' ' '{print $4}')
}

function space_required()
{
  local cmd=${RSYNC_CMD}" --dry-run --stats"
  cmd=${cmd}" --log-file="${log_file}
  cmd=${cmd}" --link-dest=../"${previous_backup}
  cmd=${cmd}" --exclude-from="${exclude_file}
  dest=${server_host}:${backup_destination}/${local_host}/WORKING
  cmd=${cmd}" "${src_folders}" "${dest}

  (>&2 echo "DEBUG: "${cmd})

  line=$(${cmd} | grep '^sent' | cut -d' ' -f2)
  line=${line//,/}

  size=$((line/1024))
  echo $size
}

function do_backup()
{
  local cmd=${RSYNC_CMD}
  cmd=${cmd}" --log-file="${log_file}
  cmd=${cmd}" --link-dest=../"${previous_backup}
  cmd=${cmd}" --exclude-from="${exclude_file}
  dest=${server_host}:${backup_destination}/${local_host}/WORKING
  cmd=${cmd}" "${src_folders}" "${dest}

  (>&2 echo "DEBUG: "${cmd})
  if [ $DEBUG -eq 0 ]
  then
    ${cmd}
  fi
}

function finish_up()
{
  local new_latest=$(date +"%Y-%m-%d-%H%M%S")
  local cmd="mv "${backup_destination}"/"${local_host}"/WORKING "${backup_destination}"/"${local_host}"/"${new_latest}
  (>&2 echo "DEBUG: "${cmd})
  if [ $DEBUG -eq 0 ]
  then
    ssh -q ${server_host} ${cmd}
  fi
}

function remove_remote_folder()
{
  local oldest = $1
  ssh -q ${server_host} rm -rf ${backup_destination}/${local_host}/${oldest}
}

function get_oldest_backup_name()
{
  local cmd="ls -d "${backup_destination}"/"${local_host}"/20* | sort | head -1"
  local ans=$(ssh -q ${server_host} ${cmd} | cut -d'/' -f5)
  (>&2 echo "get_oldest_backup_name = "${ans})
  echo ${ans}
}
function get_latest_backup_name()
{
  local cmd="ls -d "${backup_destination}"/"${local_host}"/20* | sort | tail -1"
  #echo ssh -q ${server_host} ${cmd}
  local ans=$(ssh -q ${server_host} ${cmd} | cut -d'/' -f5)
  (>&2 echo "get_latest_backup_name = "${ans})
  echo ${ans}
}

function get_backup_count()
{
  local cmd="ls -d "${backup_destination}"/"${local_host}"/20* | wc -l"
  local ans=$(ssh -q ${server_host} ${cmd})
  (>&2 echo "get_backup_count = "${ans})
  echo ${ans}
}

function enough_space()
{
  # 1 - enough, 0 - not enough
  local gigabyte=$((1024*1024))
  local enough=0
  if [ $((needed)) -gt $((gigabyte)) ] && [ $((needed)) -lt $((available)) ]
  then
    enough=1
  elif [ $((needed)) -lt $((gigabyte)) ] && [ $((gigabyte)) -lt $((available)) ]
  then
    enough=1
  fi
  (>&2 echo "enough = "$enough)
  echo $enough
}

function test()
{
  (>&2 echo "error")
  echo stdout
}

previous_backup=$(get_latest_backup_name)
echo "latest = "${previous_backup}
needed=15000
needed=$(space_required)
available=$(space_available)
echo "needed = "$needed
echo "available = "$available

#echo "TESTING"
oldest_backup=$(get_oldest_backup_name)
#backup_count=$(get_backup_count)

# remove old backups until there is either only one left
# or there is enough space for the next backup
finished=0
while [ $(get_backup_count) -gt 1 ] && [ $finished -eq 0 ]
do
  if [ $(enough_space) -eq 1 ]
  then
    finished=1
  else
    echo "DEBUG: remove_remote_folder "$(get_oldest_backup_name)
    exit 1
  fi
done

if [ $finished -eq 0 ]
then
  echo "Cannot do backup. not enough space and only 1 backup left."
  exit 1
fi

echo "Enough space available, doing backup."
do_backup

ret=$?
if [ $ret -eq $RSYNC_SUCCESS ]
then
  success=1;
elif [ $ret -eq $RSYNC_FILES_VANISHED ] || [ $success -eq $RSYNC_FILES_ALSO_VANISHED ]
then
  echo "Some files vanished during the backup."
  success=1
elif [ $ret -eq $RSYNC_FILES_COULD_NOT_BE_TRANSFERRED ]
then
  echo "Some files could not be transferred, check permissions of source files."
  success=1
elif [ $ret -eq $RSYNC_TIMEOUT_IN_DATA_SEND_RECIEVE ]
then
  echo "Problems transferring backup, disk might be full."
  success=0;
fi

if [ $success -eq 1 ]
then
  finish_up
fi
