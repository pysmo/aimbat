import unittest
import sys, os, os.path
from pysmo.aimbat.sacpickle import readPickle, zipFile, fileZipMode, pkl2sac, sac2pkl, SacDataHdrs, SacGroup
import numpy as np
import obspy as obs

# Here's our "unit tests".
class sacpickleModel(unittest.TestCase):

    def test_fileZipMode(self):
        filemode1, zipmode1 = fileZipMode('20120115.13401954.bhz.pkl')
        self.assertEqual(filemode1, 'pkl')
        self.assertEqual(zipmode1, None)

        filemode2, zipmode2 = fileZipMode('20120115.13401954.bhz.pkl.gz')
        self.assertEqual(filemode2, 'pkl')
        self.assertEqual(zipmode2, 'gz')

        filemode3, zipmode3 = fileZipMode('TA.SAC')
        self.assertEqual(filemode3, 'sac')
        self.assertEqual(zipmode3, None)

    def test_pkl2sac(self):
    	pkfile = '20120109.04071467.bhz.pkl'
      	zipmode = None

        gsac = readPickle(pkfile, zipmode)
        sacdh = gsac.saclist[0]
        dirarr = sacdh.filename.split('/')
        dirname = dirarr[0]+'/'+dirarr[1]

      	pkl2sac(pkfile, zipmode)

        #sac is default folder name for sacfiles to be put to
        self.assertTrue(os.path.isdir(dirarr[0]))
        self.assertTrue(os.path.isdir(dirname))

    def test_sac2pkl(self):
        if os.path.isfile('sac2pkl_files/Event_2011.09.15.19.31.04.080/20110915.19310408.bhz.pkl'):
            os.remove('sac2pkl_files/Event_2011.09.15.19.31.04.080/20110915.19310408.bhz.pkl')
        self.assertFalse(os.path.isfile('sac2pkl_files/Event_2011.09.15.19.31.04.080/20110915.19310408.bhz.pkl'))

        ifiles = ['sac2pkl_files/Event_2011.09.15.19.31.04.080/AR.113A.__.BHZ', 
            'sac2pkl_files/Event_2011.09.15.19.31.04.080/AR.319A.__.BHZ', 
            'sac2pkl_files/Event_2011.09.15.19.31.04.080/AR.U15A.__.BHZ', 
            'sac2pkl_files/Event_2011.09.15.19.31.04.080/AR.W13A.__.BHZ', 
            'sac2pkl_files/Event_2011.09.15.19.31.04.080/AR.X16A.__.BHZ', 
            'sac2pkl_files/Event_2011.09.15.19.31.04.080/AR.X18A.__.BHZ', 
            'sac2pkl_files/Event_2011.09.15.19.31.04.080/AZ.BZN.__.BHZ', 
            'sac2pkl_files/Event_2011.09.15.19.31.04.080/AZ.CPE.__.BHZ', 
            'sac2pkl_files/Event_2011.09.15.19.31.04.080/AZ.CRY.__.BHZ', 
            'sac2pkl_files/Event_2011.09.15.19.31.04.080/AZ.FRD.__.BHZ', 
            'sac2pkl_files/Event_2011.09.15.19.31.04.080/AZ.HWB.__.BHZ', 
            'sac2pkl_files/Event_2011.09.15.19.31.04.080/AZ.KNW.__.BHZ', 
            'sac2pkl_files/Event_2011.09.15.19.31.04.080/AZ.LVA2.__.BHZ', 
            'sac2pkl_files/Event_2011.09.15.19.31.04.080/AZ.MONP2.__.BHZ', 
            'sac2pkl_files/Event_2011.09.15.19.31.04.080/AZ.PFO.__.BHZ', 
            'sac2pkl_files/Event_2011.09.15.19.31.04.080/AZ.RDM.__.BHZ', 
            'sac2pkl_files/Event_2011.09.15.19.31.04.080/AZ.SCI2.__.BHZ', 
            'sac2pkl_files/Event_2011.09.15.19.31.04.080/AZ.SMER.__.BHZ', 
            'sac2pkl_files/Event_2011.09.15.19.31.04.080/AZ.SND.__.BHZ', 
            'sac2pkl_files/Event_2011.09.15.19.31.04.080/AZ.SOL.__.BHZ', 
            'sac2pkl_files/Event_2011.09.15.19.31.04.080/AZ.TRO.__.BHZ', 
            'sac2pkl_files/Event_2011.09.15.19.31.04.080/AZ.WMC.__.BHZ', 
            'sac2pkl_files/Event_2011.09.15.19.31.04.080/BK.CMB.00.BHZ', 
            'sac2pkl_files/Event_2011.09.15.19.31.04.080/BK.HUMO.00.BHZ', 
            'sac2pkl_files/Event_2011.09.15.19.31.04.080/BK.MCCM.00.BHZ', 
            'sac2pkl_files/Event_2011.09.15.19.31.04.080/BK.SAO.00.BHZ', 
            'sac2pkl_files/Event_2011.09.15.19.31.04.080/BK.WDC.00.BHZ']
        pkfile = 'sac2pkl_files/Event_2011.09.15.19.31.04.080/20110915.19310408.bhz.pkl'
        delta = 0.025
        zipmode = None
        sac2pkl(ifiles, pkfile, delta, zipmode)

        #check the file exists now
        self.assertTrue(os.path.isfile('sac2pkl_files/Event_2011.09.15.19.31.04.080/20110915.19310408.bhz.pkl'))

    def test_SacDataHdrs_init(self):
        instance = SacDataHdrs('sac2pkl_files/Event_2011.09.15.19.31.04.080/AR.113A.__.BHZ', 0.025)
        trace = obs.read('sac2pkl_files/Event_2011.09.15.19.31.04.080/AR.113A.__.BHZ')

        self.assertEqual(np.floor(instance.delta*1000),25)
        self.assertTrue(set(instance.data).issubset(trace[0].data))
        self.assertEqual(trace[0].stats.npts, instance.npts)

    def test_SacGroup_init(self):
        ifiles = ['sac2pkl_files/Event_2011.09.15.19.31.04.080/AR.113A.__.BHZ', 
            'sac2pkl_files/Event_2011.09.15.19.31.04.080/AR.319A.__.BHZ', 
            'sac2pkl_files/Event_2011.09.15.19.31.04.080/AR.U15A.__.BHZ', 
            'sac2pkl_files/Event_2011.09.15.19.31.04.080/AR.W13A.__.BHZ', 
            'sac2pkl_files/Event_2011.09.15.19.31.04.080/AR.X16A.__.BHZ', 
            'sac2pkl_files/Event_2011.09.15.19.31.04.080/AR.X18A.__.BHZ', 
            'sac2pkl_files/Event_2011.09.15.19.31.04.080/AZ.BZN.__.BHZ', 
            'sac2pkl_files/Event_2011.09.15.19.31.04.080/AZ.CPE.__.BHZ', 
            'sac2pkl_files/Event_2011.09.15.19.31.04.080/AZ.CRY.__.BHZ', 
            'sac2pkl_files/Event_2011.09.15.19.31.04.080/AZ.FRD.__.BHZ', 
            'sac2pkl_files/Event_2011.09.15.19.31.04.080/AZ.HWB.__.BHZ', 
            'sac2pkl_files/Event_2011.09.15.19.31.04.080/AZ.KNW.__.BHZ', 
            'sac2pkl_files/Event_2011.09.15.19.31.04.080/AZ.LVA2.__.BHZ', 
            'sac2pkl_files/Event_2011.09.15.19.31.04.080/AZ.MONP2.__.BHZ', 
            'sac2pkl_files/Event_2011.09.15.19.31.04.080/AZ.PFO.__.BHZ', 
            'sac2pkl_files/Event_2011.09.15.19.31.04.080/AZ.RDM.__.BHZ', 
            'sac2pkl_files/Event_2011.09.15.19.31.04.080/AZ.SCI2.__.BHZ', 
            'sac2pkl_files/Event_2011.09.15.19.31.04.080/AZ.SMER.__.BHZ', 
            'sac2pkl_files/Event_2011.09.15.19.31.04.080/AZ.SND.__.BHZ', 
            'sac2pkl_files/Event_2011.09.15.19.31.04.080/AZ.SOL.__.BHZ', 
            'sac2pkl_files/Event_2011.09.15.19.31.04.080/AZ.TRO.__.BHZ', 
            'sac2pkl_files/Event_2011.09.15.19.31.04.080/AZ.WMC.__.BHZ', 
            'sac2pkl_files/Event_2011.09.15.19.31.04.080/BK.CMB.00.BHZ', 
            'sac2pkl_files/Event_2011.09.15.19.31.04.080/BK.HUMO.00.BHZ', 
            'sac2pkl_files/Event_2011.09.15.19.31.04.080/BK.MCCM.00.BHZ', 
            'sac2pkl_files/Event_2011.09.15.19.31.04.080/BK.SAO.00.BHZ', 
            'sac2pkl_files/Event_2011.09.15.19.31.04.080/BK.WDC.00.BHZ']
        instance = SacGroup(ifiles, 0.025)

        self.assertEqual(len(instance.saclist), len(ifiles))
        self.assertEqual(instance.event[0], 2011) #year
        self.assertEqual(instance.event[1], 9) #month
        self.assertEqual(instance.event[2], 15) #day
        self.assertEqual(instance.event[3], 19) #hour of day






