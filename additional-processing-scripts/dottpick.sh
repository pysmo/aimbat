#!/bin/bash
#
# Run ttpick.py 
#
### xlou 03/18/2012

if [ $# -eq 0 ]; then
	echo "Usage: $0 pklfiles"
	exit
fi


for pfile in $*; do
	bh=`echo $pfile | cut -d. -f3`
	if [ $bh == bhz ] ; then
		xlim="-25 25"
	else
		xlim="-50 50"
	fi
	echo ""
	echo "--> ttpick.py $pfile"
	ttpick.py $pfile -r2 -s0 -x $xlim -g
done

rm -f evids
for pfile in $*; do
	echo $pfile | cut -d. -f1-2 >> evids
done

bhe=empty.png
for evid in `uniq evids`; do
	echo "event: $evid"
	bhz=$evid.bhz.pkl.png
	bht=$evid.bht.pkl.png
	bho=$evid.tpk.png
	if [ -f $bhz -a -f $bht ]; then
		convert +append $bhz $bht $bho
	elif [ -f $bhz ]; then
		convert +append $bhz $bhe $bho
	else
		convert +append $bhe $bht $bho
	fi
	rm -f $bhz $bht
done


