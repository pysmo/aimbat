#!/bin/bash
#
# Run ttcheck.py for each x file
#
### xlou 03/26/2012 


for evid in `ls [1-9]*x | cut -d. -f1-2 | uniq`; do
	echo ttcheck.py $evid*x -s
	ttcheck.py $evid*x -s
done

ttcheck.py [1-9]*x -m -s

