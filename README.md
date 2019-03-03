# README #

### Recent Changes ###

+ v2.0 - Feb 2019 (started) - Client Based Version to run on the Mac and backup to the server.
    * DONE - still needs a log rotate function.
    * DONE - use logging module
    * needs a scheduling system.
    * Settings.verify() needs a little work. look in to more advance json features
    * unit testing needs completing.
    * DONE - check version of python used to run this is > 3.5
    * check for filesystem support for symlinks and hardlinks
    * cater for platform specific differences and features (MacOs, Linux, Windoze?)
    
+ v0.5 - Dec 2017 - Final version of server based version
 
### What is this repository for? ###

* Quick summary - This is a simple backup solution for those with a small linux server and a laptop also running linux or macOs.

It creates backup folders like macOs TimeMachine which are full of hard links to the previous packup folder (to save space on 
the file system) before running rsync between the source and destination to update the latest backup folder.  This way it keeps
deleted files in previous backups without wasting extra space.

* Version - 0.3

* [Learn Markdown](https://bitbucket.org/tutorials/markdowndemo)

### How do I install? ###

* Download the latest tar file from the downloads folder, unpack it and run the install.py script.

* Configuration - The install.py script will create the configuration file

* Dependencies - python, rsync

* Deployment instructions - To be installed on backup destination server.

### Contribution guidelines ###

* Writing tests
* Code review
* Other guidelines

### Who do I talk to? ###

* Repo owner or admin - ianjudge1969@gmail.com
