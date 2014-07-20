#!/bin/bash
#
# Run ttdict.py related scripts: ttstats, ttpairs, ttvdist at the dir of *x
# All commands save figs instead of show()
#
### xlou 03/23/2012


sel=F
new=F

for opt in $* ; do
    if  [ $opt == "-s" ]; then
        sel=T
        echo "Select events/stations"
    fi
    if  [ $opt == "-n" ]; then
        new=T
        echo "New dtdict.pkl and dt-stats from *x files"
		rm -f dtdict.pkl dt-*
    fi
done


### get dtdict
echo "### get dtdict ###############################################################################"
if [ ! -f dtdict.pkl ]; then
	ttdict.py [1-9]*x -o dtdict.pkl
fi

### delay stats
echo "### delay stats ###############################################################################"
if [ $sel == T ]; then
	ttstats.py -i dtdict.pkl -E delete-events -A delete-events-abs -S delete-stations -M -g 
	ttstats.py -i dtdict.pkl -E delete-events -A delete-events-abs -S delete-stations -M -g -a
#	ttstats.py -i dtdict.pkl -E delete-events -A delete-events-abs -S delete-stations -M -g -m
#	ttstats.py -i dtdict.pkl -E delete-events -A delete-events-abs -S delete-stations -M -g -m -a
else
	ttstats.py -i dtdict.pkl -M -g 
	ttstats.py -i dtdict.pkl -M -g -a
#	ttstats.py -i dtdict.pkl -M -g -m
#	ttstats.py -i dtdict.pkl -M -g -m -a
fi

convert +append map-ave-dt-rel.png map-ave-dt-abs.png map-ave-dt-rel-abs.png
rm -f map-ave-dt-rel.png map-ave-dt-abs.png

echo "### delay pairs ###############################################################################"
### delay pairs
#ttpairs.py -i dtdict.pkl -p -g
#ttpairs.py -i dtdict.pkl -p -a -g
#
#if [ $sel == T ]; then
#	ttpairs.py -i dtdict.pkl -E delete-events -S delete-stations -A delete-events-abs -p -g
#	ttpairs.py -i dtdict.pkl -E delete-events -S delete-stations -A delete-events-abs -p -g -a
#fi
#

#### dtpair sep
#echo "### delay pairs sep ###########################################################################"
#if [ $sel == T ]; then
#	ttpairs.py -i dtdict.pkl -E delete-events -A delete-events-abs -S delete-stations -w -g
#	ttpairs.py -i dtdict.pkl -E delete-events -A delete-events-abs -S delete-stations -w -a -g
##	ttpairs.py -i dtdict.pkl -E delete-events -A delete-events-abs -S delete-stations -w -m -g
##	ttpairs.py -i dtdict.pkl -E delete-events -A delete-events-abs -S delete-stations -w -a -m -g
#else
#	ttpairs.py -i dtdict.pkl -w -g
#	ttpairs.py -i dtdict.pkl -w -a -g
##	ttpairs.py -i dtdict.pkl -w -m -g
##	ttpairs.py -i dtdict.pkl -w -a -m -g
#
#fi

# delay sep hist
#echo "### delay pairs dist ##########################################################################"
#if [ $sel == T ]; then
#	ttpairs.py -i dtdict.pkl -E delete-events -A delete-events-abs -S delete-stations -H -k -g 
#	ttpairs.py -i dtdict.pkl -E delete-events -A delete-events-abs -S delete-stations -H -k -m -g
#else
#	ttpairs.py -i dtdict.pkl -H -k -g 
#	ttpairs.py -i dtdict.pkl -H -k -m -g
#fi
#
####  dtdist
#echo "### delay pairs dist ##########################################################################"
#if [ ! -d stalines ]; then
#	ttvdist.py -i dtdict.pkl -w	-t 	# for ta lines
#fi
#if [ ! -f stalines/dd.d ]; then
#	ttvdist.py -i dtdict.pkl -w		# for all stations
#fi
#
#if [ $sel == T ]; then
#	ttvdist.py -i dtdict.pkl -E delete-events -A delete-events-abs -S delete-stations -s all -g
#	ttvdist.py -i dtdict.pkl -E delete-events -A delete-events-abs -S delete-stations -s all -g -a
#	ttvdist.py -i dtdict.pkl -E delete-events -A delete-events-abs -S delete-stations -s all -m -g
#	ttvdist.py -i dtdict.pkl -E delete-events -A delete-events-abs -S delete-stations -s all -m -g -a
#else
#	ttvdist.py -i dtdict.pkl -s all -g
#	ttvdist.py -i dtdict.pkl -s all -a -g
#	ttvdist.py -i dtdict.pkl -s all -m -g
#	ttvdist.py -i dtdict.pkl -s all -m -g -a
#fi
#
