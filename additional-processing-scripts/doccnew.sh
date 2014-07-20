#!/bin/bash
#
#outline for crust correction:
#-- Run "crustread.py -c" to get crustal model for stations from Crust 2.0 
#	* save ascii file for Moho depth
#	* save pickle file for crustal model
#-- Run "crustread.py -m model" to get Moho depth for NA04/NA07/Lowry or a combination
#-- Run "ccorr.py -p map/hist" for crustal correction partition
#-- Run "ccorr.py -c" for crustal correction in three types
#	* (a) Topo          : topo compared to upper crust in refmodel (for joint inversion of BW+SW)
#	* (b) Topo+Sedi     : topo + crust 2 sedi 
#	* (c) Topo+Sedi+Moho: topo + crust 2 sedi + na04-lowry moho (for BW only inversion)
#   Four more types:
#	* (d) Sedi          : (crust2 sedi compared to upper crust of the same thickness)
#	* (e) Moho          : (na04-lowry moho)
#	* (f) Topo+Moho     : (real topo + na04-lowry moho)
#	* (g) Crust2        : (crust2 all)
### xlou 03/26/2012

### three types of correction: (a) Topo (b) Topo+Sedi (c) Topo+Sedi+Moho;   for three arrays
# -c to calculate ccorr
# -C to plot      ccorr


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


####### seven types of crustal correction

sfile="loc.sta"
refmodel="iasp91"
mohomodel="na04-lowry"
ccorr.py -s $sfile -r $refmodel -m $mohomodel -c


ccs=(a b c d e f g)
tcorrs=(Topo Topo+Sedi Topo+Sedi+Moho Sedi Moho Topo+Moho Crust2)
tcorrs=(Topo Topo+Sedi Topo+Sedi+Moho Sedi"(Crust2)" Moho"(Lowry+NA04)" Topo+Moho Crust2)
n=6
for i in `seq 0 $n`; do
    cc=${ccs[$i]}
    tcorr=${tcorrs[$i]}
    ifile=sta-cc$cc-$refmodel
    plotccorr.sh $ifile "$tcorr" -p
    plotccorr.sh $ifile "$tcorr" -p -s
	#convert -append $ifile-p.png $ifile-s.png $ifile.png
    #convert -append $ifile-p.png $ifile-s.png $ifile-a.png
    #aplotccorr.sh $ifile "$tcorr" -b
    #aplotccorr.sh $ifile "" -s -b
    #convert -append $ifile-p.png $ifile-s.png $ifile-b.png
	#convert +append $ifile-a.png $ifile-b.png $ifile.pdf
    rm -f $ifile-p.png $ifile-s.png $ifile-a.png $ifile-b.png
done


