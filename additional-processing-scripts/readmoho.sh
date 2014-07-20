#!/bin/bash
#
# Read moho depths values for the entire US from NA04 and NA07.
# Output regularly spaced xyz points and a GMT binary grd.
# 
### xlou 03/08/2012


if [ $# -eq 0 ]; then
	echo "Usage: $0 model[na04/na07/lowry/crust2]"
	exit
fi
model=`echo $1 | tr "[:lower:]" "[:upper:]"`

#if [ ! -f $model ]; then
#	echo "File $model does not exist. Exit."
#	exit
#fi

# determine program to use
if [ $model == NA04 ]; then
	prog=sns
elif [ $model == NA07 ]; then
	prog=tom2gmt
fi

ofile=moho-`echo $model | tr "[:upper:]" "[:lower:]"`
grd=$ofile.grd
flag=-a


ymin=20
ymax=55
xmin=-127
xmax=-65
dx=.25
dy=.25


# get xyz file for moho depth:
if [ -f $ofile ]; then
	echo "$ofile already exists!"
else
echo "Running: $prog $flag $model"

cat << eoi | $prog $flag $model
2
$ofile
$ymin $ymax $xmin $xmax
$dx $dy
eoi
fi

# convert yz to grd
if [ -f $grd ]; then
	echo "$grd already exists!"
else
	echo "Converting: $ofile --> $grd"
	xyz2grd $ofile -I$dx/$dy -R$xmin/$xmax/$ymin/$ymax -G$grd
fi

