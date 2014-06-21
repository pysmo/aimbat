c ---------------------------------------------------------------------
c . . . . . . . . . BEGIN SUBROUTINE DELAZ  . . . . . . . . . . . . . .
c#  delaz - calculate geocentric postitions, distances, and azimuths
      subroutine delaz(lat, lon, delta, az0, az1, iflag)
c      implicit undefined (a-z)
c
c   ken creager 6/11/87
c
c
      real lat, lon
      real delta, az0, az1
      integer iflag
      real st0, ct0, phi0
      real st1, ct1, dlon
      real sdlon, cdlon
      real cz0
      real sdelt, cdelt
      save st0, ct0, phi0
 
c . . refpt - store the geocentric coordinates of the refeernce point
      if (iflag .eq. 0) then
         st0 = cos(lat)
         ct0 = sin(lat)
         phi0 = lon
 
c . . delaz - calculate the geocentric distance, azimuths
      else if (iflag .eq. 1) then
         ct1 = sin(lat)
         st1 = cos(lat)
         sdlon = sin(lon - phi0)
         cdlon = cos(lon - phi0)
         cdelt = st0*st1*cdlon + ct0*ct1
         call cvrtop (st0*ct1-st1*ct0*cdlon, st1*sdlon, sdelt, az0)
         delta = atan2(sdelt, cdelt)
         call cvrtop (st1*ct0-st0*ct1*cdlon, -sdlon*st0, sdelt, az1)
         if (az0 .lt. 0.0) az0 = az0 + (2.0*3.14159265)
         if (az1 .lt. 0.0) az1 = az1 + (2.0*3.14159265)
 
c . . back-calculate geocentric coordinates of secondary point from delta, az
      else if (iflag .eq. 2) then
         sdelt = sin(delta)
         cdelt = cos(delta)
         cz0 = cos(az0)
         ct1 = st0*sdelt*cz0 + ct0*cdelt
         call cvrtop (st0*cdelt-ct0*sdelt*cz0, sdelt*sin(az0),st1,dlon)
         lat = atan2(ct1, st1)
         lon = phi0 + dlon
         if(abs(lon) .gt. 3.14159265)
     #       lon = lon - sign((2.0*3.14159265), lon)
 
      end if
      return
      end
c . . . . . . . . . END SUBROUTINE DELAZ  . . . . . . . . . . . . . . .
c ---------------------------------------------------------------------
c . . . . . . . . . BEGIN SUBROUTINE COORTR . . . . . . . . . . . . . .

      subroutine coortr (alatrd, alonrd,  alatdg, alondg,  i)
c     alatrd (geocentric lat. radian), alonrd (long. radian)
c     alatdg (geographical lat. degree), alogdg (long. degree)
c     transformation  (alatdg,alondg) to (alatrd,alonrd) if  i=0
c     transformation  (alatrd,alonrd) to (alatdg, alondg) if  i=1
      if (i)  30, 30, 31
   30 alatrd = 0.1745329252 e-1 * alatdg
      alonrd = 0.1745329252 e-1 * alondg
      bbb  =  abs( alatdg )
      if ( bbb.ge.89.9 ) go to 32
      aaa = 0.9933056 * tan ( alatrd )
      alatrd = atan ( aaa )
   32 return
   31 bbb = abs( alatrd )
      if ( bbb.ge.1.57 )  go to 33
   34 aaa = tan ( alatrd ) / 0.9933056
      alat2 = atan (aaa )
      go to 35
   33 alat2 = alatrd
   35 alatdg = alat2* 57.29577951
      alondg = alonrd * 57.29577951
      return
      end
c . . . . . . . . . END SUBROUTINE COORTR . . . . . . . . . . . . . . .
c ---------------------------------------------------------------------
c . . . . . . . . . END SUBROUTINE COORTR . . . . . . . . . . . . . . .
c# cvrtop - convert from rectangular to polar coordinates
      subroutine cvrtop(x, y, r, theta)
c (input)
      real x, y
c (output - may overlay x, y)
      real r, theta
      real rad
      real hypot
      rad = hypot(x, y)
      theta = atan2(y, x)
      r = rad
      return
      end
c hypot - euclidian distance, accurately and avoiding overflow
      real function hypot(a, b)
      real a, b
c
      real abs, l, s, t
c
c set s, l to be absolutely smallest, largest values
      l = abs(a)
      s = abs(b)
      if (s .le. l) goto 1
         t = s
         s = l
         l = t
   1  continue
c
c compute and return distance
      if (l .ne. 0.0) goto 2
         hypot = 0.0
         return
   2  continue
      s = s/l
      hypot = l*sqrt(s*s+1.0)
      return
      end

      integer function  lunit()
c     find an unopened fortran unit number between 5 and 100
      logical lopen
      do 1 lunit=12,99
      inquire(unit=lunit,opened=lopen)
      if (.not. lopen) return
    1 continue
      lunit=0
      write(*,*)'failed to find an unopenned unit between 5 and 99'
      return
      end

      subroutine find (x,xt,n,ians)
c
c     x is a monotonically increasing vector of dimension n.
c     xt is greater than or equal to x(ians) but less than
c     x(ians+1).
c
      dimension x(n)
      if (xt .le. x(1)) go to 104
      if (xt .ge. x(n)) go to 105
      il=1
      im=n
  102 itst=im-il
      if (itst .gt. 1) go to 100
      ians=il
      go to 103
  100 ihalf=(im+il)/ 2
      if(xt .ge. x(ihalf)) go to 101
      im=ihalf
      goto 102
  101 il=ihalf
      go to 102
  104 ians=1
      go to 103
  105 ians=n
  103 return
      end
