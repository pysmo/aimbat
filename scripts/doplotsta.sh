#!/bin/bash
#
# Run plotsta.sh for multiple delay files
# Now also does relative and absolute (.dtp and .adtp) delay files
#
### xlou 11/25/2011 || TREV Updated 05/15/14


dtfiles=`ls [1-9]*.dt?`
echo $dtfiles
for dtfile in $dtfiles; do
	plotsta.sh $dtfile -d
done

phase=`echo $dtfiles | cut -d" " -f 1 | cut -d. -f3 | cut -c 3`

figs=`ls [1-9]*.dt$phase.png`
echo convert $figs dt$phase.gif
convert $figs dt$phase.gif
rm -f $figs

rm -f $figs
rm -f .gmtdefaults .gmtcommands gmt.conf gmt.history
