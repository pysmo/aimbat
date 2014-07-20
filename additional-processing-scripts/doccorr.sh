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

sfile=loc.sta
mohomodel="na04-lowry"
#mohomodel="na04"

for dir in sta-xa sta-xr sta-ta; do
	cd $dir
	pwd
	for refmodel in xc35 iasp91; do
		rm -f sta-cc?-$refmodel
		ccorr.py -s $sfile -r $refmodel -m $mohomodel -c #-C 
	done
	cd ..
done
