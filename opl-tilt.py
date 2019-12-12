from geoptics.guis.qt import main as gui
from geoptics.elements.line import Line
from geoptics.elements.vector import Vector, Point

import geoptics.elements.rays
import geoptics.elements.sources
import geoptics.guis.qt.sources
import geoptics.guis.qt.regions
import geoptics.guis.qt.rays
import geoptics.guis.qt.counterpart

from operator import itemgetter
from sys import float_info
import math

import weakref

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPainterPath, QPainterPathStroker, QPen
from PyQt5.QtWidgets import (
	QGraphicsItem,
	QGraphicsPathItem,
	QStyle,
	QStyleOptionGraphicsItem,
)


class RayOPL(geoptics.elements.rays.Ray):
	# Set the drawn OPL here (dirty workaround, I'm aware)
	OPL = 250.0

	def __init__(self, line0=None, s0=100, source=None, n=None, tag=None):
		geoptics.elements.rays.Ray.__init__(self, line0, s0, source, n, tag)
		self.L = self.OPL


# Copy from geoptics.guis.qt.rays._GRay, subclassing did not work right away
@geoptics.guis.qt.counterpart.g_counterpart
class _GQtRayOPL(QGraphicsPathItem):
	"""The graphical class corresponding to :class:`.Ray`."""

	# note: @g_counterpart will add a keyword argument, "element"
	def __init__(self, **kwargs):
		QGraphicsPathItem.__init__(self, **kwargs)

		self.setAcceptHoverEvents(True)
		self.setFlag(QGraphicsItem.ItemIsSelectable, True)
		# Rays stay just below the source,
		# without any need to set Z-value explicitly
		# This avoid selection problems (ray is always behind handles)
		self.setFlag(QGraphicsItem.ItemStacksBehindParent, True)

		# pen for normal state
		self.pen_normal = QPen(Qt.blue, 1.5, Qt.SolidLine)
		self.pen_normal.setCosmetic(True)  # thickness does not scale
		self.setPen(self.pen_normal)
		# pen for hover state
		self.pen_hover = QPen(Qt.gray, 1.5, Qt.SolidLine)
		self.pen_hover.setCosmetic(True)  # thickness does not scale

		# will be used in shape()
		self.stroker = QPainterPathStroker()

		self._selected = False

	def g_draw(self):
		self.prepareGeometryChange()
		# prevent BSPtree corruption (Qt crash)
		self.e.source.g.prepareGeometryChange()
		path = QPainterPath()
		# begin at the beginning
		p0 = self.e.parts[0].line.p
		path.moveTo(p0.x, p0.y)
		# add lines
		for i,part in enumerate(self.e.parts):
			if math.isinf(part.s):
				# something large, but not inf, for Qt
				# make sure the ray extends more than the whole scene
				scene_rect = self.scene().sceneRect()
				s = 2 * max(scene_rect.width(), scene_rect.height())

				# Drawn length is dependent on defined OPL
				s = self.e.L - sum([p.s * p.n for p in self.e.parts[0:i]])

			else:
				s = part.s
			path.lineTo(part.line.p.x + part.line.u.x * s,
						part.line.p.y + part.line.u.y * s)

		# update to the new path
		self.setPath(path)

	def g_add_part(self, u, s, n=None):
		RayOPL.add_part(self.e, u, s, n)
		self.g_draw()

	def g_change_s(self, part_number, new_s):
		RayOPL.change_s(self.e, part_number, new_s)
		self.g_draw()

	def hoverEnterEvent(self, event):
		"""Overload QGraphicsPathItem method."""

		self.setPen(self.pen_hover)
		QGraphicsPathItem.hoverEnterEvent(self, event)

	def hoverLeaveEvent(self, event):
		"""Overload QGraphicsPathItem method."""

		self.setPen(self.pen_normal)
		QGraphicsPathItem.hoverEnterEvent(self, event)

	def itemChange(self, change, value):
		"""Overload QGraphicsPathItem method."""

		if (change == QGraphicsItem.ItemSelectedChange):
			# usually setSelected should not be called here, but
			# setSelected has been overriden and does not call the base method
			self.setSelected(value)
			# return False to avoid the deselection of the pointhandle
			# (multiple selection seems impossible without holding ctrl)
			return False
		# forward event
		return QGraphicsPathItem.itemChange(self, change, value)

	def paint(self, painter, option, widget=None):
		"""Overload QGraphicsPathItem method."""

		new_option = QStyleOptionGraphicsItem(option)
		# suppress the "selected" state
		# this avoids the dashed rectangle surrounding the ray when selected
		new_option.state = QStyle.State_None
		QGraphicsPathItem.paint(self, painter, new_option, widget)

	def shape(self):
		"""Overload QGraphicsPathItem method."""

		# by default, the shape is the path,
		# but closed, even if the path is a line
		# then sometimes the ray seems hovered, even when mouse is not on it
		# to avoid that, we need to reimplement shape,
		# with a QPainterPathStroker which
		# creates a shape that closely fits the line
		return self.stroker.createStroke(self.path())

	def setSelected(self, selected):
		"""Overload QGraphicsPathItem method."""

		# override base method, without calling it
		# otherwise the selection of pointHandle
		# deselected the ray and vice-versa
		# (multiple selection seems impossible without holding ctrl)
		# FIXME: should not use the element(.g) here. Find another way.
		self.e.source.g.setSelected(selected)
		self._selected = selected

	def isSelected(self):
		"""Overload QGraphicsPathItem method."""

		return self._selected


@geoptics.guis.qt.counterpart.GOverload("add_part", "change_s", "draw")
class QtRayOPL(RayOPL):
	"""" Copied from geoptics.guis.qt.rays.Ray """

	"""Ray of light.

		This is the Ray that should be instanciated,
		in the :mod:`.guis.qt` backend.

		.. note::
			Regular users should not use Ray directly,
			but instead use one of the sources in :mod:`.qt.sources`.
		"""

	def __init__(self, line0=None, s0=100, source=None, n=None, tag=None,
				 zvalue=100, **kwargs):
		g = _GQtRayOPL(element=self, **kwargs)
		# rays must be children of the source, in order to
		# - be removed when source is removed from scene
		# - inherit the zvalue of the source
		# - be added to the scene when the source is added
		g.setParentItem(source.g)
		# the _G object has a Qt parent, so will be deleted by the C++ part
		# keep only a weak reference, otherwise there may be deletion races
		self._g_wr = weakref.ref(g)
		RayOPL.__init__(self, line0, s0, source, n, tag)
		self.source = source
		self.g.g_draw()
		self.set_tag(tag)

	def __del__(self):
		"""Cleanup upon deletion."""

		# if the deletion comes from the qt side, self.g is None
		if self.g:
			self.source.g.prepareGeometryChange()
			self.g.scene().removeItem(self.g)

	@property
	def g(self):
		"""Return the corresponding graphical item."""

		return self._g_wr()


class BeamOPL(geoptics.elements.sources.Beam):
	def __init__(self, line_start=None, s_start=None, line_end=None, s_end=None, N_inter=0, scene=None, tag=None):
		"""" Override Beam.__init__ to explicitly inject QtRayOPL """
		geoptics.elements.sources.Source.__init__(self, scene=scene, tag=tag)

		self.rays = [QtRayOPL(source=self) for _ in range(N_inter + 2)]
		self.N_inter = N_inter
		self.set(line_start=line_start, line_end=line_end, s_start=s_start, s_end=s_end)


class QtBeamOPL(BeamOPL):
	def __init__(self, line_start=None, s_start=None, line_end=None, s_end=None, N_inter=0,
				scene=None, tag=None, zvalue=100, **kwargs):
		# do not pass the scene here
		self.g = geoptics.guis.qt.sources._GBeam(element=self, zvalue=zvalue, **kwargs)
		# The element __init__ method will call self.scene.add,
		# which will need self.g
		BeamOPL.__init__(self,
			line_start=line_start, s_start=s_start,
			line_end=line_end, s_end=s_end,
			N_inter=N_inter, scene=scene, tag=tag
		)


if __name__ == "__main__":
	# Modified https://github.com/ederag/geoptics/blob/master/t_geo.py

	gui = gui.Gui()
	size = 1e4
	gui.scene.g.setSceneRect(-size / 100, -size / 100, size, size)

	scene = gui.scene

	# refractive index for rp1
	n = 1.5

	# rp1
	rp1 = geoptics.guis.qt.regions.Polycurve(n=n, scene=scene)
	m1 = Point(70, 60)
	rp1.start(m1)
	m2 = Point(70, 190)
	rp1.add_line(m2)
	m3 = Point(110, 190)
	rp1.add_line(m3)
	m4 = Point(110, 60)
	tg4 = Vector(10, -20)
	rp1.add_arc(m4, tg4)
	rp1.close()

	# tracé d'un rayon
	p0 = Point(10, 50)
	u0 = Vector(108, 0)
	s0 = 3
	n0 = 1.0

	p1 = Point(10, 80)
	u1 = Vector(108, 0)
	source2 = QtBeamOPL(
		line_start=Line(p0, u0), line_end=Line(p1, u1),
		s_start=100, s_end=100, N_inter=6
	, scene=scene
	)
	source2.translate(dy=40)

	scene.propagate()

	# launch the gui
	gui.start()
