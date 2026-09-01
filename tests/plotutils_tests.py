import sys
import unittest

from pysmo.aimbat.pickphase import PickPhaseMenu
from pysmo.aimbat.qualctrl import getAxes, getDataOpts

test_filename = "20120109.04071467.bhz.pkl"

# ############################################################################### #
#                                     MODELS                                      #
# ############################################################################### #


class plotutilsModel(unittest.TestCase):
    def test_getOptions(self):
        pass


# ############################################################################### #
#                                     MODELS                                      #
# ############################################################################### #


# ############################################################################### #
#                                      VIEWS                                      #
# ############################################################################### #


class plotutilsView(unittest.TestCase):
    @unittest.skip(
        "PickPhaseMenu.on_select relies on SpanSelector.visible, removed in matplotlib 3.7. "
        "Needs the GUI overhaul (see HANDOFF.md step 5)."
    )
    def test_timeSelector_ignore(self):
        sys.argv[1:] = [test_filename]
        gsac, opts = getDataOpts()
        opts.labelqual = True
        axs = getAxes(opts)
        ppm = PickPhaseMenu(gsac, opts, axs)

        ppm.on_select(-3, 4.3)
        self.assertEqual(ppm.axpp.get_xlim(), (-3, 4.3))


# ############################################################################### #
#                                      VIEWS                                      #
# ############################################################################### #
