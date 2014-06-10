import unittest

import sys
#sys.path.append('aimbat')
from pysmo.aimbat.sacpickle import zipFile, pkl2sac

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
    	print tt
    	self.failIf(False)

    def pkl2sac_test(self):
    	pkfile = 'test-load.bhz.pkl'
    	zipmode = 'None'
    	pkl2sac(pkfile, zipmode)
    	self.failIf(False)


def main():
    unittest.main()

if __name__ == '__main__':
    main()