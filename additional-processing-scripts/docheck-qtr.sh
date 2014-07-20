#!/bin/bash
#
# Run ttcheck.py and dottpick.sh for each year and quarter
#
### xlou 03/18/2012 

if [ $# -eq 0 ]; then
	echo "Usage: $0 year1 year2 mw60"
	echo "       -c (ttcheck)"
	echo "       -p (ttpick)"
	exit
fi

ttcheck=F
ttpick=F


for opt in $* ; do
	if  [ $opt == "-c" ]; then
		ttcheck=T
		echo "Run ttcheck.py"
	fi
	if  [ $opt == "-p" ]; then
		ttpick=T
		echo "Run ttpick.py"
	fi
done


year1=$1
year2=$2
mw=$3
# date begin/end for each quarter of year
qtrs=(1 2 3 4)
name=(0[1-3] 0[4-6] 0[7-9] 1[0-2])

for year in `seq $year1 $year2`; do
	dir=ta$year$mw
	cd $dir
	pwd
	# ttcheck
	if [ $ttcheck == T ]; then
		ttcheck.py *x -m -s
		for q in `seq 0 3`; do
			echo "year $year quarter ${qtrs[$q]}: "
			ls $year${name[$q]}*x
			nf=`ls $year${name[$q]}*x |wc -l`
			if [ $nf -gt 0 ]; then
				ttcheck.py $year${name[$q]}*x -s
				#convert $year${name[$q]}*dta.png dta$year"q"${qtrs[$q]}.gif
			fi
		done
		#convert dta"$year"q?.gif dta"$year".gif
	fi

	# ttpick
	if [ $ttpick == T ]; then
		dottpick.sh *pkl
		#convert *pkl.png dtpick"$year".gif
	fi
	cd ..
done

