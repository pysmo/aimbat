@echo off
setlocal
set seelectFile=%1
set deselctFile=%2
shift
shift
gmt pscoast -R%1/%2/%3/%4     -N1 -JL%5/%6/%7/%8/12 -K -Bf10a30/f5a20:."STATIONS":neWS -W0.45p,0/0/0 -G230/195/170 -Df -V -X1.0 -Y1.0> MAP.ps
gmt psxy -W0.4p,000/000/000 -: -JL%5/%6/%7/%8/12 -K -R -G0/255/0 -Sc0.15 -O -V %seelectFile% >> MAP.ps
gmt psxy -W0.4p,000/000/000 -: -JL%5/%6/%7/%8/12 -K -R -G255/0/0 -Sc0.15 -O -V %deselctFile% >> MAP.ps
