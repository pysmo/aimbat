gmt pscoast -R${3}/${4}/${5}/${6}     -N1 -JL${7}/${8}/${9}/${10}/12 -K -Bf10a30/f5a20:."STATIONS":neWS -W0.45p,0/0/0 -G230/195/170 -Df -V -X1.0 -Y1.0> MAP.ps
gmt psxy -W0.4p,000/000/000 -: -JL${7}/${8}/${9}/${10}/12 -K -R -G0/255/0 -Sc0.15 -O -V ${1} >> MAP.ps
gmt psxy -W0.4p,000/000/000 -: -JL${7}/${8}/${9}/${10}/12 -K -R -G255/0/0 -Sc0.15 -O -V ${2} >> MAP.ps

open MAP.ps
