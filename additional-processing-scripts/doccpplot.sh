#!/bin/bash
#
# plot cc partition in GMT using two scales (-a.png -b.png) 
#
### xlou 11/28/2012

#cd ~/work/na/data/crust/sta-all

cfiles="sta-ccpart-crust2 sta-ccpart-crust2intpol sta-ccpart-crust2intpol-na04-lowry"
#cfiles="sta-ccpart-crust2"
tcorrs=(All Sediment Topography MohoDepth Layering)
nt=4

ftag=tmpfile
for cfile in $cfiles; do
	for i in `seq 0 $nt`; do
		ia=`echo $i*2+5 |bc`
		ib=`echo $i*2+6 |bc`
		ifile="$ftag$i"
		awk '{print $1,$2,$3,$4,$('$ia'),$('$ib')}' $cfile > $ifile
		tcorr=${tcorrs[$i]}
		aplotccorr.sh $ifile "$cfile==>$tcorr"
		aplotccorr.sh $ifile "" -s
		convert -append $ifile-p.png $ifile-s.png $ifile-a.png
		aplotccorr.sh $ifile "$cfile==>$tcorr" -b
		aplotccorr.sh $ifile "" -s -b
		convert -append $ifile-p.png $ifile-s.png $ifile-b.png
		convert +append $ifile-a.png $ifile-b.png $cfile-p$i.png
		#rm -f $ifile-p.png $ifile-s.png $ifile-a.png $ifile-b.png $ifile
	done
	convert +append $ftag[0-4]-a.png $cfile-pa.pdf
	convert +append $ftag[0-4]-b.png $cfile-pb.pdf
	convert $cfile-p[0-4].png $cfile-pp.pdf
	rm -f $cfile-p[0-b].png
done

#exit

for i in `seq 0 $nt`; do
	ifile="$ftag$i"
	rm -f $ifile-p.png $ifile-s.png $ifile-a.png $ifile-b.png $ifile
done
