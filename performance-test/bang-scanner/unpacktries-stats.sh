#!/bin/sh

d=`dirname "$0"`

( echo unpacker,result,time ; (grep '^try_' | sed 's/try_.*\[\(unpack.*\)\]: \(.*\) = \(.*\)/\1,\2,\3/')) | python3 "$d"/unpacktries-stats.py 

