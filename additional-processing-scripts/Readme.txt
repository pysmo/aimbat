=================================================================================

This directory contains programs to process xfiles from MCCC and EHB residuals.

This is a replacement of the original fortran codes in procx directory.
Most programs are in py except getime, which is wrapped by f2py for usage in py.
Script getime.py calls the f2py lib getime.so to do same function of getime.f

See the docstring of the .py files or can run %prog -h for help.

=================================================================================

Todo:
  ANF arrivals
  crust correction??

=================================================================================
Main changes:
  -- .f .f90 --> .py
  -- centralized formats/filenames in ttcommon.py
  -- reverse to orignal filenames: loc.sta, ref.teqs, ref.tsta...
  -- abandon the long unreadable PDE/HDS string for hypocenter and origin time
     read/write space separted numbers
  -- added files: ref.evst, ref.csta

=================================================================================
Files:

  loc.sta   -> LOCation of STAtions
  ref.rays  -> REFerence Travel-time Rays (source-receiver pair).
  ref.tsta  -> REFerence Travel-time STAtion locations
  ref.teqs  -> REFerence Travel-time EarthQuakeS
  ref.tcals -> REFerence Travel-time CALibration terms for Stations
  ref.tcale -> REFerence Travel-time CALibration terms for Earthquakes
                                 (i.e. earthquake relocation terms)
    counts of stations/events added to ref.tcals and ref.tcale
  ref.evst  -> location of event and station (lon/lat) pairs for GMT plotting
  ref.csta  -> crust/topo correction of travel times for each station

=================================================================================
Programs:

ttcommon.py:
  Common functionalities, config for file names and formats.

mccc.py:
  Run MCCC to get MCCC derived relative arrival times.
  <-- loc.sta, event.list
  --> ?.mc


selehb.py:
  Read and select EHB residuals from ISC.
  <-- EHB residual files organized by years
  --> selected res file

ehb2mccc.py:
  Convert EHB residuals to MCCC format.
  <-- selected res file
  --> loc.sta, *.mc

roldmccc.py:
  Read old mccc format into new format of mccc.py
  --> loc.sta, *.mc

mccc2delay.py
  Calculate theoretical 1D travel times to get relative delay times.
  Precalulated crust and topo corrections (in file ref.csta).
  <-- loc.sta, *.mc, ref.csta
  --> *.sx, *.px

procx.py
  Combine xfiles for use of program SETPAR.
  <-- loc.sta, *.sx 
  --> ref.tsta, ref.teqs, ref.rays, ref.tcale, ref.tcals, ref.evst
      ref.evst contain s event/staion pair location for GMT plotting


xlou 05/09/2011

=================================================================================
Scripts/module after MCCC delay times.

ttdict.py
  This script/module deals with MCCC delay times which are saved in python dict.

ttcheck.py
  Check S/P delay ratio and distribution.

stasep.py
  Separate stations into two groups, one west and the other east of the Rocky Mountains.

xlou 03/04/2012

ttstats.py
  Write delay time statistics files

ttpairs.py
  Plot delay time pairs.

xlou 03/21/2012

=================================================================================

Crust corrections

crust.py
  Module for Moho depth or crustal thickness from models

crustread.py
  Script to get Moho depth from model: crust2, NA04, NA07, Lowry or a combination. 


xlou 03/10/2012
=================================================================================
=================================================================================
=================================================================================
=================================================================================


### xlou 05/04/2011
Bug on getime.
If an event has depth < 0.5 or so, and it is not the first time to call getime, 
  there is error or Bad interpolation and the travel time is wrong.

I can not figure out why.
Have to run mccc2delay.py for events shallower than 1km.

xlou@yushu:~/work/na/tomo/data/tt/ehb/20110427/s$ mccc2delay.py  19611030.02163270.mc  19611030.08332935.mc
--> Calculate take-off angles from surface P and S velocities: 5.20 3.00 km/s
    No crust/topo correction on travel time.
['19611030.02163270.mc', '19611030.08332935.mc']
--MCCC to delay:  19611030.02163270.mc
--MCCC to delay:  19611030.08332935.mc
 Bad interpolation on Pg      
 Bad interpolation on PgPg    
 Bad interpolation on Sg      
 Bad interpolation on SgSg    
 Bad interpolation on PgS     
 Bad interpolation on Pg      
 Bad interpolation on PgPg    
 Bad interpolation on Sg      
 Bad interpolation on SgSg    
 Bad interpolation on PgS     
xlou@yushu:~/work/na/tomo/data/tt/ehb/20110427/s$ mccc2delay.py 19611030.08332935.mc  19611030.02163270.mc
--> Calculate take-off angles from surface P and S velocities: 5.20 3.00 km/s
    No crust/topo correction on travel time.
['19611030.08332935.mc', '19611030.02163270.mc']
--MCCC to delay:  19611030.08332935.mc
--MCCC to delay:  19611030.02163270.mc


mccc2delay.py 19611030.02163270.mc 19611030.08332935.mc
mccc2delay.py 19611030.08332935.mc 19611030.02163270.mc




xlou@yushu:~/work/na/tomo/data/tt/ehb/20110427/s$ mccc2delay.py 19611030.08332935.mc
--> Calculate take-off angles from surface P and S velocities: 5.20 3.00 km/s
    No crust/topo correction on travel time.
['19611030.08332935.mc']
--MCCC to delay:  19611030.08332935.mc
73.794 54.223 0.5
PAL    S 73.794 54.223 0.5 1111.40124512 -1.09264469147 [5.2000000000000002, 3.0]
WMO    S 73.794 54.223 0.5 1233.5715332 -0.997186481953 [5.2000000000000002, 3.0]

xlou@yushu:~/work/na/tomo/data/tt/ehb/20110427/s$ mccc2delay.py 19611030.08332935.mc
--> Calculate take-off angles from surface P and S velocities: 5.20 3.00 km/s
    No crust/topo correction on travel time.
['19611030.08332935.mc']
--MCCC to delay:  19611030.08332935.mc
73.794 54.223 0.0
PAL    S 73.794 54.223 0.0 1111.55761719 -1.09292793274 [5.2000000000000002, 3.0]
WMO    S 73.794 54.223 0.0 1233.72961426 -0.997625291348 [5.2000000000000002, 3.0]


### Xiaoting Lou 05/05/2011

