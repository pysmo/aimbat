import unittest
import sys, os
from pysmo.aimbat.sacpickle import readPickle, zipFile, pkl2sac
from pysmo.aimbat.qualctrl import getOptions


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

    def testFour(self):
    	output = getOptions()
    	#print output
    	print 'YOLO'
    	self.failIf(False)

def main():
    unittest.main()

if __name__ == '__main__':
    main()