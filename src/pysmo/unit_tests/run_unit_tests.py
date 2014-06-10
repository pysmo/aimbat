import unittest
from qualctrl_tests import qualctrlTests
from sacpickle_tests import sacpickleTests


suite_qualctrl = unittest.TestLoader().loadTestsFromTestCase(qualctrlTests)
suite_sacpickle = unittest.TestLoader().loadTestsFromTestCase(sacpickleTests)

unittest.TextTestRunner(verbosity=2).run(suite_qualctrl)
#unittest.TextTestRunner(verbosity=2).run(suite_sacpickle)