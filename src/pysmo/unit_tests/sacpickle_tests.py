import unittest
import sys, os
from pysmo.aimbat.sacpickle import readPickle, zipFile, pkl2sac


# Here's our "unit tests".
class sacpickleTests(unittest.TestCase):

    def testThree(self):
    	tt = zipFile('gz')
    	self.failIf(False)

    def test_pkl2sac(self):
    	pkfile = 'test-load.bhz.pkl'
      	zipmode = None

        gsac = readPickle(pkfile, zipmode)
        sacdh = gsac.saclist[0]
        dirarr = sacdh.filename.split('/')
        dirname = dirarr[0]+'/'+dirarr[1]

      	pkl2sac(pkfile, zipmode)

        #sac is default folder name for sacfiles to be put to
        sacFolderExists = os.path.isdir(dirarr[0]) 
        sacInnerFolderExists = os.path.isdir(dirname) 

        self.failUnless(sacFolderExists)
        self.failUnless(sacInnerFolderExists)

def main():
    unittest.main()

if __name__ == '__main__':
    main()