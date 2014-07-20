#!/bin/sh
# Do mccc2delay for three types of travel time correction
# xlou 05/04/2011

if [ $# -eq 1 ]; then
	mod=$1
else
	mod=iasp91
fi

if [ $# -eq 2 ]; then
	year=$2
else
	year=*
fi


echo "Reference model: $mod"

dirs=(tcorr-ellip tcorr-topo tcorr-toposedi tcorr-toposedimoho)
tags=("" "-c sta-cca-$mod" "-c sta-ccb-$mod" "-c sta-ccc-$mod")

for i in `seq 0 3`; do
	dir=${dirs[$i]}
	if [ ! -d $dir ]; then
		mkdir $dir
	fi
	tag=${tags[$i]}
	echo "Correction type/dir: $dir"
	echo "mccc2delay.py mc/$year*mc* -m $mod $tag "
	mccc2delay.py mc/$year*mc* -m $mod $tag
	mv [1-9]*x $dir
	rsync -avz loc.sta $dir
done

