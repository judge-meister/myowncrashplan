#!/bin/bash

#
# create a tar file containing installation files
#

. ./VERSION

TARFILE=myocp-$VERSION.tar.gz

cd ./src

tar czvf ../downloads/$TARFILE .

