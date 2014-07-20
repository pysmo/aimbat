#!/bin/bash
#
#outline for crust correction:
#
#-- Run crustread.py to get crustal model for stations from Crust 2.0
#	* save ascii file for Moho depth
#	* save pickle file for crustal modell#-- Run crustread.py to get Moho depth for NA04/NA07/Lowry or a combination
#-- Run ccorr.py -p for crustal correction partition
#-- Run ccorr.py -c for crustal correction in three types
#	* (a) Topo: 		for jiont inversion of BW+SW
#	* (b) Topo+Sedi: 	for joint inv too?
#	* (c) Topo+Sedi+Moho: for BW only inversion 
#
### xlou 03/26/2012

# For all stations
###

stafile="loc.sta"
####### get crustal model for stations
if [ ! -f sta-cmodel-crust2.pkl -o ! -f sta-cmodel-crust2intpol.pkl ]; then
	crustread.py -c -s $stafile
fi

####### get and plot moho for stations
models="crust2 crust2intpol na04 na07 lowry na04-lowry na07-lowry"
for mod in $models; do
	sfile="sta-moho-$mod"
	if [ ! -f $sfile ]; then
		crustread.py -m $mod -s $stafile
		plotmoho-points.sh $sfile
	fi
done

####### compare moho depths from models
crustread.py -M -g
crustread.py -C -g
####### compare sediment and moho depths for crust2
crustread.py -S -g


####### cc partition
ccorr.py -p map -g
ccorr.py -p hist -g


####### three types of crustal correction

sfile="loc.sta"
refmodel="iasp91"
mohomodel="na04-lowry"
ccorr.py -s $sfile -r $refmodel -m $mohomodel -c

ccs=(a b c d e f g)
tcorrs=(Topo Topo+Sedi Topo+Sedi+Moho Sedi Moho Topo+Moho Crust2)
tcorrs=(Topo Topo+Sedi Topo+Sedi+Moho Sedi"(crust2)" Moho"(Lowry+NA04)" Topo+Moho Crust2)
n=6

for i in `seq 0 $n`; do
    cc=${ccs[$i]}
    tcorr=${tcorrs[$i]}
    ifile=sta-cc$cc-$refmodel
    aplotccorr.sh $ifile "$tcorr"
    aplotccorr.sh $ifile "" -s
    convert -append $ifile-p.png $ifile-s.png $ifile-a.png
    aplotccorr.sh $ifile "$tcorr" -b
    aplotccorr.sh $ifile "" -s -b
    convert -append $ifile-p.png $ifile-s.png $ifile-b.png
	convert +append $ifile-a.png $ifile-b.png $ifile.pdf
    rm -f $ifile-p.png $ifile-s.png $ifile-a.png $ifile-b.png
done

