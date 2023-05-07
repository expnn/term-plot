# -*- coding: utf-8 -*-

# see https://github.com/jktr/matplotlib-backend-kitty.git
# https://github.com/matplotlib/matplotlib/blob/4bdae2e004b29d075f96a7dbbee918f7dfb13ed1/lib/matplotlib/backends/backend_template.py#L149

"""
A fully functional, do-nothing backend intended as a template for backend
writers.  It is fully functional in that you can select it as a backend e.g.
with ::
    import matplotlib
    matplotlib.use("template")
and your program will (should!) run without error, though no output is
produced.  This provides a starting point for backend writers; you can
selectively implement drawing methods (`~.RendererTemplate.draw_path`,
`~.RendererTemplate.draw_image`, etc.) and slowly see your figure come to life
instead having to have a full-blown implementation before getting any results.
Copy this file to a directory outside the Matplotlib source tree, somewhere
where Python can import it (by adding the directory to your ``sys.path`` or by
packaging it as a normal Python package); if the backend is importable as
``import my.backend`` you can then select it using ::
    import matplotlib
    matplotlib.use("module://my.backend")
If your backend implements support for saving figures (i.e. has a `print_xyz`
method), you can register it as the default handler for a given file type::
    from matplotlib.backend_bases import register_backend
    register_backend('xyz', 'my_backend', 'XYZ File Format')
    ...
    plt.savefig("figure.xyz")
"""

import sys
# noinspection PyProtectedMember
from matplotlib.backend_bases import FigureManagerBase, _Backend
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib import interactive, is_interactive
# noinspection PyProtectedMember
from matplotlib._pylab_helpers import Gcf
from term_plot.imgcat import imgcat

# XXX heuristic for interactive repl
if sys.flags.interactive:
    interactive(True)


########################################################################
#
# The following functions and classes are for pyplot and implement
# window/figure managers, etc.
#
########################################################################


class FigureManagerImgcat(FigureManagerBase):
    """
    Helper class for pyplot mode, wraps everything up into a neat bundle.
    For non-interactive backends, the base class is sufficient.  For
    interactive backends, see the documentation of the `.FigureManagerBase`
    class for the list of methods that can/should be overridden.
    """

    def show(self):
        canvas = self.canvas
        imgcat(canvas.figure)


class FigureCanvasImgcat(FigureCanvasAgg):
    """
    The canvas the figure renders into.  Calls the draw and print fig
    methods, creates the renderers, etc.
    Note: GUI templates will want to connect events for button presses,
    mouse movements and key presses to functions that call the base
    class methods button_press_event, button_release_event,
    motion_notify_event, key_press_event, and key_release_event.  See the
    implementations of the interactive backends for examples.
    Attributes
    ----------
    figure : `matplotlib.figure.Figure`
        A high-level Figure instance
    """

    # The instantiated manager class.  For further customization,
    # ``FigureManager.create_with_canvas`` can also be overridden; see the
    # wx-based backends for an example.
    manager_class = FigureManagerImgcat


########################################################################
#
# Now just provide the standard names that backend.__init__ is expecting
#
########################################################################

@_Backend.export
class _BackendICatAgg(_Backend):
    FigureCanvas = FigureCanvasImgcat
    FigureManager = FigureManagerImgcat

    # Noop function instead of None signals that
    # this is an "interactive" backend
    mainloop = lambda: None

    # XXX: `draw_if_interactive` isn't really intended for
    # on-shot rendering. We run the risk of being called
    # on a figure that isn't completely rendered yet, so
    # we skip draw calls for figures that we detect as
    # not being fully initialized yet. Our heuristic for
    # that is the presence of axes on the figure.
    @classmethod
    def draw_if_interactive(cls):
        manager = Gcf.get_active()
        if is_interactive() and manager.canvas.figure.get_axes():
            cls.show()

    @classmethod
    def show(cls, *args, **kwargs):
        _Backend.show(*args, **kwargs)
        Gcf.destroy_all()
