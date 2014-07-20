#!/bin/bash
# Run domccc2delay.sh and dottdict.sh
### xlou 03/26/2012

sel=F
if [ $# -eq 0 ]; then
	echo "Usage: $0 model (iasp91)"
	exit
fi

for opt in $* ; do
    if  [ $opt == "-s" ]; then
        sel=T
        echo "Select events/stations"
    fi
done

mod=$1
echo "Running domc2d.sh with reference model: $mod"

pwd
ln -s ../sta-cc?-$mod .
ln -s ../delete-events* .
ln -s ../delete-stations* .
domccc2delay.sh $mod >& log-mc2d.txt

dirs="tcorr-ellip tcorr-topo tcorr-toposedi tcorr-toposedimoho"	
for dir in $dirs; do
	cd $dir
	pwd
	ln -s ../loc.sta .
	ln -s ../delete-events* .
	ln -s ../delete-stations .
	if [ $sel == T ]; then
		dottdict.sh -n -s >& log-dict.txt		# select events/stations
	else
		dottdict.sh -n >& log-dict.txt
	fi
	cd .. 
done
