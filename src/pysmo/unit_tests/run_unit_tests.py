import unittest
from qualctrl_tests import qualctrlModel, qualctrlView
from sacpickle_tests import sacpickleModel
from plotutils_tests import plotutilsView


# ############################################################################### #
#                                     MODELS                                      #
# ############################################################################### #

"""Run the models"""
suite_qualctrl_m = unittest.TestLoader().loadTestsFromTestCase(qualctrlModel)
suite_sacpickle_m = unittest.TestLoader().loadTestsFromTestCase(sacpickleModel)

# ------------------------------------------------------------------------------- #

"""Set the models"""
#unittest.TextTestRunner(verbosity=2).run(suite_qualctrl_m)
unittest.TextTestRunner(verbosity=2).run(suite_sacpickle_m)

# ############################################################################### #
#                                     MODELS                                      #
# ############################################################################### #







# ############################################################################### #
#                                      VIEWS                                      #
# ############################################################################### #

"""Set the views"""
suite_qualctrl_sortingClass_v = unittest.TestLoader().loadTestsFromTestCase(qualctrlView.sortingClass)
suite_qualctrl_filterClass_v = unittest.TestLoader().loadTestsFromTestCase(qualctrlView.filterClass)
suite_plotutils_v = unittest.TestLoader().loadTestsFromTestCase(plotutilsView)

# ------------------------------------------------------------------------------- #

"""Run the views"""
#unittest.TextTestRunner(verbosity=2).run(suite_qualctrl_sortingClass_v)
#unittest.TextTestRunner(verbosity=2).run(suite_qualctrl_filterClass_v)
#unittest.TextTestRunner(verbosity=2).run(suite_plotutils_v)


# ############################################################################### #
#                                      VIEWS                                      #
# ############################################################################### #