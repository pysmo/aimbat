import unittest

import sys, os
#sys.path.append('aimbat')
from pysmo.aimbat.sacpickle import readPickle, zipFile, pkl2sac

# Here's our "unit".
def IsOdd(n):
    return n % 2 == 1

# Here's our "unit tests".
class IsOddTests(unittest.TestCase):

    def testOne(self):
        self.failUnless(IsOdd(1))

    def testTwo(self):
        self.failIf(IsOdd(2))

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