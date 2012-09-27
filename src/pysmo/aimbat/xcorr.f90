!!!---------------------------------------------------------------------!!!
! Filename: xcorr.f90
!   Author: Xiaoting Lou
!    Email: xlou@u.northwestern.edu
!
! Copyright (c) 2009-2012 Xiaoting Lou
!!!---------------------------------------------------------------------!!!
! Module to calculate cross correlation function of two time series with the same length.
!      c(k) = sum_i  x(i) * y(i+k)
!           where k is the time shift of y relative to x.
!Delay time, correlation coefficient, and polarity at maximum correlation are returned.
!
! Added suport to correlation polarity to allow negative correlation maximum.
! Output ccpol=1 if positive or ccpol=-1 if negative. xlou 03/2011
!
! Use numpy.f2py to wrap the code into to a library that can be used in python.
! $ f2py -c -m xcorrf90 xcorr.f90 --fcompiler=gfortran
!
!
!:copyright:
!	Xiaoting Lou
!
!:license:
!	GNU General Public License, Version 3 (GPLv3) 
!	http://www.gnu.org/licenses/gpl.html
!!!---------------------------------------------------------------------!!!


!!!---------------------------------------------------------------------!!!
function crosscorr(x, y, n, k)
! Cross-correlation of array x and y for a given time shift k.
implicit none
integer :: n, k
real(8), dimension(0:n-1) :: x, y
real(8) crosscorr
if (k.ge.0) then
    crosscorr = dot_product(x(0:n-1-k), y(k:n-1))
else
    crosscorr = dot_product(x(-k:n-1), y(0:n-1+k))
endif
end function crosscorr
!!!---------------------------------------------------------------------!!!


!!!---------------------------------------------------------------------!!!
subroutine xcorr_full(x, y, n, shift, delay, ccmax, ccpol)
! Cross-correlation of array x and y.
! Return time shift, correlation coefficient, and polarity at maximum correlation.
implicit none
real(8) :: crosscorr
integer :: n, shift, delay, ccpol
real(8), dimension(0:n-1) :: x, y
real(8) :: cc, ccmax, ccmin
integer :: k, kmin
!f2py intent(in)  :: x, y, n, shift
!f2py intent(out) :: delay, ccmax, ccpol
!f2py intent(hide):: c, k, kmin, ccmin

shift = 1
ccmax = 0
ccmin = 0
kmin = 0
do k = -n+1,n-1,shift
    cc = crosscorr(x,y,n,k)   
    if (cc.gt.ccmax) then
        ccmax = cc
        delay = k
    endif
    if (cc.lt.ccmin) then
        ccmin = cc
        kmin = k
    endif
enddo
if (ccmax.gt.-ccmin) then
    ccpol = 1
else
    ccmax = -ccmin
    delay = kmin
    ccpol = -1
endif
ccmax = ccmax/sqrt( dot_product(x,x) * dot_product(y,y) )

end subroutine xcorr_full
!!!---------------------------------------------------------------------!!!


!!!---------------------------------------------------------------------!!!
subroutine xcorr_fast(x, y, n, shift, delay, ccmax, ccpol)
! Fast cross-correlation using 1 level of coarse shift.
implicit none
integer :: n, shift, delay, ccpol
real(8), dimension(0:n-1) :: x, y
real(8) :: cc, ccmax, ccmin
integer :: s, k, k0, k1, kmin
integer, dimension(0:1) :: shifts
real(8) :: crosscorr
!f2py intent(in)  :: x, y, n, shift
!f2py intent(out) :: delay, ccmax, ccpol
!f2py intent(hide):: cc, s, k, k0, k1, kmin, ccmin

shifts=(/shift,1/)
ccmax = 0
ccmin = 0
kmin = 0
do s = 0,size(shifts)-1
    if (s.eq.0) then
        k0 = 1-n
        k1 = n-1
    else
        k0 = delay-shifts(s-1)
        k1 = delay+shifts(s-1)
    endif
    do k = k0, k1, shifts(s)
        cc = crosscorr(x,y,n,k)
        if (cc.gt.ccmax) then
            ccmax = cc
            delay = k
        endif
        if (cc.lt.ccmin) then
            ccmin = cc
            kmin = k
        endif
    enddo
if (ccmax.gt.-ccmin) then
    ccpol = 1
else
    ccmax = -ccmin
    delay = kmin
    ccpol = -1
endif
enddo

ccmax = ccmax/sqrt( dot_product(x,x) * dot_product(y,y) )

end subroutine xcorr_fast
!!!---------------------------------------------------------------------!!!


!!!---------------------------------------------------------------------!!!
subroutine xcorr_faster(x, y, n, shift, delay, ccmax, ccpol)
! Faster cross-correlation only for time lags around zero.
implicit none
integer :: n, shift, delay, k, kmin, ccpol
real(8), dimension(0:n-1) :: x, y
real(8) :: cc, ccmax, ccmin
real(8) :: crosscorr
!f2py intent(in)  :: x, y, n, shift
!f2py intent(out) :: delay, ccmax, ccpol
!f2py intent(hide):: cc, k, kmin, ccmin

ccmax = 0
ccmin = 0
kmin = 0
do k = -shift, shift, 1
    cc = crosscorr(x,y,n,k)   
    if (cc.gt.ccmax) then
        ccmax = cc
        delay = k
    endif
    if (cc.lt.ccmin) then
        ccmin = cc
        kmin = k
    endif
enddo
if (ccmax.gt.-ccmin) then
    ccpol = 1
else
    ccmax = -ccmin
    delay = kmin
    ccpol = -1
endif
ccmax = ccmax/sqrt( dot_product(x,x) * dot_product(y,y) )

end subroutine xcorr_faster
!!!---------------------------------------------------------------------!!!



