#!/bin/bash
#
# Plot station map or delay times if -d option is given.
#
### xlou 11/25/2011 || TREV Updated 03/05/14

#gmtset FONT_LABEL 10p,Helvetica,black # gmt5
gmtset FONT_LABEL 10p
gmtset FONT_ANNOT_PRIMARY 10p
gmtset FONT_ANNOT_SECONDARY 8p
gmtset FONT_TITLE	14p


if [ $# -eq 0 ]; then
        echo "Usage: $0 ifile (loc.sta or dtfile) title options"
		echo "       -d (delay time file) "
		echo "       -n (name of station) "
        exit
fi

ifile=$1
if [ $# -ge 2 ]; then
	tag=`echo $2 | cut -c1`
	if [ $tag == "-" ]; then
		title=$ifile
	else
		title=$2
	fi
else
	title=$ifile
fi

echo "ifile: $ifile"
echo "title: $title"

plotdelay=F
sdelay=F
plotsname=F

fig="$ifile".eps

for opt in $* ; do
	if  [ $opt == "-n" ]; then
		plotsname=T
		echo "Plot station name"
	fi
	if  [ $opt == "-d" ]; then
		plotdelay=T
		fig=$ifile.eps
		flen=`echo $ifile | wc -c`
		flen1=`echo "$flen-1" |bc`
		phase=`echo $ifile | cut -c $flen1-$flen1`
	fi
	if  [ $opt == "-s" ]; then
		sdelay=T
	fi
done

lat1=`gmtinfo $ifile -T6/1 | cut -c 3-40 | cut -f1 -d /`
lat2=`gmtinfo $ifile -T6/1 | cut -c 3-40 | cut -f2 -d /`
lon1=`gmtinfo $ifile -T6/2 | cut -c 3-40 | cut -f1 -d /`
lon2=`gmtinfo $ifile -T6/2 | cut -c 3-40 | cut -f2 -d /`
lat0=`echo $lat1 $lat2 | awk '{print ($1+$2)/2}'`
lon0=`echo $lon1 $lon2 | awk '{print ($1+$2)/2}'`
latdiff=`echo $lat1 $lat2 | awk '{print ($2-$1)}'`

if [ $latdiff -le 10 ]; then
	tick=2f1
else 
	tick=10f5
fi

reg=$lon1/$lon2/$lat1/$lat2
proj=L$lon0/$lat0/$lat1/$lat2/5.5i
dcpt=delay.cpt
psbasemap -R$reg -J$proj -B$tick:."$title":WSEn -X3 -Y12 -K -P > $fig
pscoast -R -J -A1000 -W0.5 -K -P -Di -O -G222 -N1/0.6p -N2/.3p -N3/.1p >> $fig

### plot stations or color-coded by delays
if [ $plotdelay == F ]; then
	echo "Plot station loc file: $ifile --> $fig"
	if [ $plotsname == F ]; then
		symb=t.14
		stcol=red
		cat $ifile | awk '{print $3,$2}' | psxy -R -J -K -P -O -S$symb -G$stcol -W.1p,black >> $fig 
	else
		symb=t.07
		stcol=red
		cat $ifile | awk '{print $3,$2}' | psxy -R -J -K -P -O -S$symb -G$stcol -W.1p,black >> $fig 
		cat $ifile | cut -c 5-200 | awk '{print $3, $2, 2.5, 0, 2, "BC", $1}' | pstext -R -J -K -P -O -N >> $fig
	fi
else
	echo "Plot delay time file: $ifile --> $fig  (Phase: $phase)"

	dtm=0.00
	if [ $phase == 'p' ]; then
		#dt1=-0.6; dt2=0.6; dt=0.3
		dt1=-1.5; dt2=1.5; ddt=0.5
		if [ $dtm == '0.00' ] ; then
			label="P Delay [s]"
		else
			label="P Delay $pm $dtm [s]"
		fi
	else
		#dt1=-2; dt2=2; dt=1
		dt1=-4.5; dt2=4.5; ddt=1.5
		if [ $dtm == '0.00' ] ; then
			label="S Delay [s]"
		else
			label="S Delay $pm $dtm [s]"
		fi
		#label='S Delay [s]'
	fi
	makecpt -Cpolar -T"$dt1/$dt2/$ddt" -Z -N > $dcpt
	echo "label: $label"
	symb=c.14

	cat $ifile | awk '{print $3,$2,$4}' |psxy -R -J -C$dcpt -S$symb -K -P -O -N >> $fig
	psscale -D13.95/3/4/0.2 -B.2:"$label": -C$dcpt -O -X.35 -Y5 -K -E >> $fig

fi

echo 0 0 | psxy -R -J -P -O >> $fig

ps2raster -Tg -A $fig
if [ $plotsname == T ]; then
	ps2raster -Tf -A $fig
fi

rm -f $fig 
rm -f $cpt
rm -f .gmtcommands* .gmtdefaults* gmt.conf gmt.history

open $ifile.png


