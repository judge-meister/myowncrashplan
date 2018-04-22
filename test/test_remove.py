#!/usr/bin/env python

import os, shutil, sys, stat

DRY_RUN = ""

def log(str):
    print "%s\n" % str


def tidyup(datedir):
    """remove the unfinished latest datedir"""
    def remove_readonly(func, path, excinfo):
        """onerror func to fix problems when using rmtree"""
        log("remove_readonly - %s" % path)
        parent = os.path.dirname(path)
        mode = os.stat(path).st_mode
        os.system("ls -ld \"%s\" " % parent)
        os.system("ls -ld \"%s\" " % path)
        print "ADD S_IWUSR" 
        os.chmod(parent, mode | stat.S_IRWXU)
        os.system("ls -ld \"%s\" " % parent)
        os.chmod(path, mode | stat.S_IRWXU)
        os.system("ls -ld \"%s\" " % path)
        func(path)

    shutil.rmtree(datedir, onerror=remove_readonly)
    

def createNextBackupFolder(datedir, backupdir):
    """create a new backup folder by using hard links"""
    try:
        if DRY_RUN != "":
            print "create new backup folder %s" % datedir
        os.mkdir(datedir)
    except:
        log("Problems creating new backup dir %s" % datedir)
        raise
        return False
    
    log("Creating Next Backup Folder %s" % (datedir))
    for root, dirs, files in os.walk('LATEST/', topdown=False, followlinks=False):
        dstpath = os.path.join(backupdir, datedir, root[7:])
        p=''
        for x in root[7:].split('/'):
            p=p+x
            if os.path.islink(os.path.join(backupdir, datedir, p)):
                print p,' is a link'
            else:
                pass #print p,' is a dir'
            p=p+'/'
        
        if not os.path.exists(dstpath):
            os.makedirs(dstpath)
        
        for name in files:
            src = os.path.join(backupdir, root, name)
            dst = os.path.join(backupdir, datedir, root[7:], name)
            os.link(src, dst)
            if not os.path.islink(src):
                atime = os.stat(src).st_atime
                mtime = os.stat(src).st_mtime
                mode = os.stat(src).st_mode
                os.utime(dst, (atime, mtime))
        
        for name in dirs:
            src = os.path.join(backupdir, root, name)
            atime = os.stat(src).st_atime
            mtime = os.stat(src).st_mtime
            mode = os.stat(src).st_mode
            dst = os.path.join(backupdir, datedir, root[7:], name)
            if not os.path.islink(src):
                try:
                    os.makedirs(dst, mode)
                except OSError:
                    os.chmod(dst, mode)
                os.utime(dst, (atime, mtime))
            else:
                os.link(src, dst)
    return True



if __name__ == '__main__':
    
    newdir = "2017-12-25-100001"
    backupdir = "/zdata/myowncrashplan"
    os.chdir(backupdir)
    if createNextBackupFolder(newdir, backupdir):
        tidyup(newdir)
    