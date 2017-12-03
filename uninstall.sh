#!/bin/bash

sudo rm -f /usr/local/bin/myowncrashplan.sh /etc/logrotate.d/myowncrashplan 

rm -f ~/.myowncrashplanrc 

(crontab -l 2>/dev/null | grep -v myowncrashplan) | crontab -