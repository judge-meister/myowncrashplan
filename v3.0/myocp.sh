#!/bin/bash

# /opt/local/bin/rsync -av --stats --dry-run --log-file=/Users/judge/.myocp/backup.log
#     --link-dest=../2019-04-21-200903 --bwlimit=2500 --timeout=300 --delete
#     --delete-excluded --exclude-from=/Users/judge/.myocp/myocp_excl
#     /Users/judge 192.168.0.7:/zdata/myowncrashplan/Prometheus.local/WORKING
#     | grep '^sent' | cut -d' ' -f2

TRUE=1
FALSE=0

#DEBUG=$TRUE
DEBUG=$FALSE

server_host=192.168.0.7
local_host=$(hostname)
backup_destination=/zdata/myowncrashplan
log_file=/Users/judge/.myocp/backup.log
exclude_file=/Users/judge/.myocp/myocp_excl
# src_folders should be configurable
src_folders="/Users/judge"
previous_backup=

RSYNC_CMD="/opt/local/bin/rsync -av --stats --bwlimit=2500 --timeout=300 --delete --delete-excluded "
RSYNC_SUCCESS=$FALSE
RSYNC_FILES_VANISHED=24
RSYNC_FILES_ALSO_VANISHED=6144
RSYNC_FILES_COULD_NOT_BE_TRANSFERRED=23
RSYNC_TIMEOUT_IN_DATA_SEND_RECIEVE=30

function space_available()
{
  kb=$(ssh ${server_host} df | grep ${backup_destination} | awk -F' ' '{print $4}')
  echo $((kb*1024))
}

function space_required()
{
  local cmd=${RSYNC_CMD}" --dry-run"
  cmd=${cmd}" --log-file="${log_file}
  cmd=${cmd}" --link-dest=../"${previous_backup}
  cmd=${cmd}" --exclude-from="${exclude_file}
  dest=${server_host}:${backup_destination}/${local_host}/WORKING
  cmd=${cmd}" "${src_folders}" "${dest}

  [ $DEBUG -eq $TRUE ] && (>&2 echo "DEBUG: "${cmd})
  echo ${cmd} >> ${log_file}

  line=$(${cmd} | grep '^Total transferred file size:')
  (>&2 echo "INFO: "${line})
  line=$(echo ${line} | cut -d':' -f2)
  line=${line//,/}
  size=${line//bytes/}

  echo $size
}

function do_backup()
{
  local ret=-1
  local cmd=${RSYNC_CMD}
  cmd=${cmd}" --log-file="${log_file}
  cmd=${cmd}" --link-dest=../"${previous_backup}
  cmd=${cmd}" --exclude-from="${exclude_file}
  dest=${server_host}:${backup_destination}/${local_host}/WORKING
  cmd=${cmd}" "${src_folders}" "${dest}

  [ $DEBUG -eq $TRUE ] && (>&2 echo "DEBUG: "${cmd})
  echo ${cmd} >> ${log_file}

  if [ $DEBUG -eq $FALSE ]
  then
    [ $DEBUG -eq $TRUE ] && (>&2 echo "INFO:" $(${cmd}))
    [ $DEBUG -ne $TRUE ] && ${cmd} >/dev/null 2>&1
    ret=$?
    line=$(grep 'Total transferred file size:' ${log_file} | tail -1 | cut -d' ' -f4-)
    (>&2 echo "INFO: "${line})
  fi
  echo $ret
}

function finish_up()
{
  local new_latest=$(date +"%Y-%m-%d-%H%M%S")
  local cmd="mv "${backup_destination}"/"${local_host}"/WORKING "${backup_destination}"/"${local_host}"/"${new_latest}
  [ $DEBUG -eq $TRUE ] && (>&2 echo "DEBUG: "${cmd})
  if [ $DEBUG -eq $FALSE ]
  then
    ssh -q ${server_host} ${cmd}
  fi
}

function remove_remote_folder()
{
  local oldest = $1
  ssh -q ${server_host} rm -rf ${backup_destination}/${local_host}/${oldest}
}

function get_backup_list()
{
  local cmd="ls -d "${backup_destination}"/"${local_host}"/20* | sort | $*"
  local ans=$(ssh -q ${server_host} ${cmd} | cut -d'/' -f5)
  [ $DEBUG -eq $TRUE ] && (>&2 echo "DEBUG: get_backup_list        = "${ans})
  echo ${ans}
}
function get_oldest_backup_name()
{
  ans=$(echo $(get_backup_list head -1))
  [ $DEBUG -eq $TRUE ] && (>&2 echo "DEBUG: get_oldest_backup_name = "${ans})
  echo ${ans}
}
function get_latest_backup_name()
{
  ans=$(echo $(get_backup_list tail -1))
  [ $DEBUG -eq $TRUE ] && (>&2 echo "DEBUG: get_latest_backup_name = "${ans})
  echo ${ans}
}

function get_backup_count()
{
  local cmd="ls -d "${backup_destination}"/"${local_host}"/20* | wc -l"
  local ans=$(ssh -q ${server_host} ${cmd})
  [ $DEBUG -eq $TRUE ] && (>&2 echo "DEBUG: get_backup_count = "${ans})
  echo ${ans}
}

function enough_space()
{
  # 1 - enough, 0 - not enough
  local gigabyte=$((1024*1024*1024))
  local enough=$FALSE
  [ $DEBUG -eq $TRUE ] && (>&2 echo "DEBUG: gigabyte = "$gigabyte)
  if [ $((needed)) -gt $((gigabyte)) ] && [ $((needed)) -lt $((available)) ]
  then
    enough=$TRUE
  elif [ $((needed)) -lt $((gigabyte)) ] && [ $((gigabyte)) -lt $((available)) ]
  then
    enough=$TRUE
  fi
  [ $DEBUG -eq $TRUE ] && (>&2 echo "DEBUG: enough = "$enough" (0=True 1=False)")
  echo $enough
}


previous_backup=$(get_latest_backup_name)
#echo "INFO: Latest Backup          = "${previous_backup}
echo "INFO: Calculating Space Required ..."
needed=15000
needed=$(space_required)
available=$(space_available)
echo "INFO: Space Required         = "$needed
echo "INFO: Remote Space Available = "$available

oldest_backup=$(get_oldest_backup_name)

# remove old backups until there is either only one left
# or there is enough space for the next backup
finished=$FALSE
if [ $(enough_space) -eq $FALSE ]
then
  while [ $(get_backup_count) -gt 1 ] && [ $finished -eq $FALSE ]
  do
    if [ $(enough_space) -eq $TRUE ]
    then
      finished=$TRUE
    else
      echo "INFO: remove_remote_folder "$(get_oldest_backup_name)" [Not implemented yet!]"
      exit 1
    fi
  done
fi

if [ $(enough_space) -eq $FALSE ]
then
  echo "INFO: Cannot do backup. not enough space and only 1 backup left."
  exit 1
fi

echo "INFO: Enough space available, so doing backup."
ret=$(do_backup)
[ $DEBUG -eq $TRUE ] && (>&2 echo "DEBUG: do_backup returned "$ret)

success=$FALSE
if [ $ret -eq $RSYNC_SUCCESS ]
then
  success=$TRUE
elif [ $ret -eq $RSYNC_FILES_VANISHED ] || [ $ret -eq $RSYNC_FILES_ALSO_VANISHED ]
then
  echo "Some files vanished during the backup."
  success=$TRUE
elif [ $ret -eq $RSYNC_FILES_COULD_NOT_BE_TRANSFERRED ]
then
  echo "Some files could not be transferred, check permissions of source files."
  success=$TRUE
elif [ $ret -eq $RSYNC_TIMEOUT_IN_DATA_SEND_RECIEVE ]
then
  echo "Problems transferring backup, disk might be full."
  success=$FALSE;
else
  echo "do_backup run in DEBUG."
  success=$FALSE
fi

if [ $success -eq $TRUE ]
then
  finish_up
fi
end_avail=$(space_available)
echo "INFO: Remote Space Available = "${end_avail}
[ $DEBUG -eq $TRUE ] && (>&2 echo "DEBUG: scale=3; ${available}-${end_avail}/${needed}")
decrease=$(echo "scale=3; (${available}-${end_avail})/${needed}"| bc -l )
echo "INFO: Decrease in space available = "${decrease}" * Space Required."

