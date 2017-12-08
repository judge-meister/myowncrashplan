#!/bin/bash

sudo rm -f /usr/local/bin/myowncrashplan.py /etc/logrotate.d/myowncrashplan 

rm -f ~/.myowncrashplan.ini

(crontab -l 2>/dev/null | grep -v myowncrashplan) | crontab -