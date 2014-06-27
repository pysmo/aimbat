import unittest
from qualctrl_tests import qualctrlModel, qualctrlView
from sacpickle_tests import sacpickleModel
from plotutils_tests import plotutilsView
from pickphase_tests import pickphaseView
from filtering_tests import filteringModel


# ############################################################################### #
#                                     MODELS                                      #
# ############################################################################### #

"""Set the models"""
suite_qualctrl_m = unittest.TestLoader().loadTestsFromTestCase(qualctrlModel)
suite_sacpickle_m = unittest.TestLoader().loadTestsFromTestCase(sacpickleModel)
suite_filtering_m = unittest.TestLoader().loadTestsFromTestCase(filteringModel)

# ------------------------------------------------------------------------------- #

"""Run the models"""
unittest.TextTestRunner(verbosity=2).run(suite_qualctrl_m)
unittest.TextTestRunner(verbosity=2).run(suite_sacpickle_m)
unittest.TextTestRunner(verbosity=2).run(suite_filtering_m)


# ############################################################################### #
#                                     MODELS                                      #
# ############################################################################### #







# ############################################################################### #
#                                      VIEWS                                      #
# ############################################################################### #

"""Set the views"""
suite_qualctrl_sortingClass_v = unittest.TestLoader().loadTestsFromTestCase(qualctrlView.sortingClass)
suite_qualctrl_filterClass_v = unittest.TestLoader().loadTestsFromTestCase(qualctrlView.filterClass)
suite_pickphase_saveClass_v = unittest.TestLoader().loadTestsFromTestCase(pickphaseView)
suite_plotutils_v = unittest.TestLoader().loadTestsFromTestCase(plotutilsView)

# ------------------------------------------------------------------------------- #

"""Run the views"""
unittest.TextTestRunner(verbosity=2).run(suite_qualctrl_sortingClass_v)
unittest.TextTestRunner(verbosity=2).run(suite_qualctrl_filterClass_v)
unittest.TextTestRunner(verbosity=2).run(suite_plotutils_v)
unittest.TextTestRunner(verbosity=2).run(suite_pickphase_saveClass_v)


# ############################################################################### #
#                                      VIEWS                                      #
# ############################################################################### #






