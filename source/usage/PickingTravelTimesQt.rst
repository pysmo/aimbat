Alternative Qt GUI for Measuring Arrival Times
----------------------------------------------

The `Matplotlib <http://matplotlib.org/contents.html>`_ GUI is slow for interactive plotting.
An additional GUI based on `pyqtgraph <http://www.pyqtgraph.org/>`_ was built since v1.0.0 to speed up plotting. 
Similar to the old GUI, run::
    aimbat-qttpick <path-to-pkl-file>
to launch the Qt GUI. Phase of the seismogram (``P`` or ``S``), if not given in command line, can be automatically found based on file names including ``BHZ`` or ``BHT``. Here is aGn example snapshot:

.. image:: images/qttpick_gui.png

The AIMBAT philosophy of using the five-step (``Align``, ``Pick``, ``Sync``, ``Refine``, and ``Finalize``) procedure for automated and interactive phase arrival time measurement is the same. 

Some GUI behavior remains the same:

* the phase picking steps of ``Align``, ``Pick``, ``Sync``, ``Refine``, and ``Finalize``.
* mouse clicking waveforms to change trace selection status.
* keyboard interaction: ``t[0-9]`` to pick time, and ``w`` to set time window.
* Click Button `Sac P2` to overlay all traces relative to time picks

Some components are different:

* Choose sort and filter options in a parameter tree and apply in the same GUI window.
* All traces plotted in one long page, instead of multiple pages. 
* Still Possible to plot a subset of traces. Click button to add more traces to the plotting window.
* `Pyqtgraph mouse events <http://www.pyqtgraph.org/documentation/mouse_interaction.html>`_: e.g., right mouse button drag to zoom in and out.
* Time window is plotted as a `pyqtgraph.LinearRegionItem <http://www.pyqtgraph.org/documentation/graphicsItems/linearregionitem.html>`_ instead of Matplotlib Span Selector. To change time window size, just drag either side line and move. Still press key ``w`` to set time window.
* A vertical hair indicating the time axis value is always plotted follow the mouse movement.

In the above example, 37 selected seismograms are plotted initially. During the arrival time measurement procedure, traces sorting order is changed after time window size or sorting parameters are changed. Trace 37, 38, 39 are missing in the GUI. You can optionally click ``Plot More Traces`` Button to fill the gap. You can also zoom out vertically and plot more traces.

Here is an example of filtering seismograms. First choose filtering parameters in the parameter tree and test on the stack by clicking Button ``Confirm_Filt_Parameters`` and Button ``Filter on Stack/Traces``. Then applied filter to traces after parameters are finalized.

.. image:: images/qttpick_gui_filter_stack.png

.. image:: images/qttpick_gui_filter_trace.png


Some QC tools are available in this Qt GUI. Click Button ``Sac P1`` and ``Sac P2`` to plot traces relative to four time picks T0, T1, T2, and T3. Click Button ``Plot Delay Times`` to plot absolute delay times in a map view. 

.. image:: images/qttpick_gui_p1.png

.. image:: images/qttpick_gui_p2.png

.. image:: images/20110915.19310408.mcp.png

More details might be added here in the future.

