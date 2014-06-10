import unittest
import sys, os
from pysmo.aimbat.sacpickle import readPickle, zipFile, pkl2sac
from pysmo.aimbat.qualctrl import getOptions, getDataOpts
from sacpickle_tests import sacpickleTests

# Here's our "unit tests".
class qualctrlTests(unittest.TestCase):

    def test_getOptions(self):
    	sys.argv[1:] = ['test-load.bhz.pkl']
    	opts = getOptions()
        print opts[0]
    	self.assertIsNone(opts[0].twin_on)
        self.assertEqual(opts[0].maxnum,(37,3))
        self.assertIsNone(opts[0].nlab_on)

    def test_getDataOpts(self):
    	sys.argv[1:] = ['test-load.bhz.pkl']
    	gsac, opts = getDataOpts()
        print dir(gsac)

# def main():
#     unittest.main()

suite1 = unittest.TestLoader().loadTestsFromTestCase(qualctrlTests)
suite2 = unittest.TestLoader().loadTestsFromTestCase(sacpickleTests)
unittest.TextTestRunner(verbosity=2).run(suite1)
unittest.TextTestRunner(verbosity=2).run(suite2)

# if __name__ == '__main__':
#     main()