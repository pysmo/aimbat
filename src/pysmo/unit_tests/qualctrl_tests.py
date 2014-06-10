import unittest
import sys, os
from pysmo.aimbat.sacpickle import readPickle, zipFile, pkl2sac
from pysmo.aimbat.qualctrl import getOptions, getDataOpts

# Here's our "unit tests".
class qualctrlTests(unittest.TestCase):

    def test_getOptions(self):
    	sys.argv[1:] = ['test-load.bhz.pkl']
    	output = getOptions()
    	self.failIf(False)

    def test_getDataOpts(self):
    	sys.argv[1:] = ['test-load.bhz.pkl']
    	gsac, opts = getDataOpts()
        print dir(gsac)

def main():
    unittest.main()

if __name__ == '__main__':
    main()