Alternative Qt GUI for Measuring Arrival Times
----------------------------------------------

The `Matplotlib <http://matplotlib.org/contents.html>`_ GUI is slow for interactive plotting.
An additional GUI based on `pyqtgraph <http://www.pyqtgraph.org/>` was built since v1.0.0 to speed up plotting. 
Similar to the old GUI, run ``aimbat-qttpick -p P <path-to-pkl-file>`` for ``BHZ`` files or ``aimbat-qttpick -p S <path-to-pkl-file>`` for ``BHT`` files. Here is an example of the new GUI:

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
* `Pyqtgraph mouse events <http://www.pyqtgraph.org/documentation/mouse_interaction.html>`_: e.g., right mouse button  drag to zoom in and out.
