#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
 Draw interactive arrows in GIMP, using a path as a guide for where to draw.

================================================================================
 Inspired by 'arrowdesigner-0.5' of Akkana Peck, at 
     http://www.shallowsky.com/software and 'arrow.scm' of W. Berengar, thanks.
 'ArrowsCreator' version 0.1 by Robert Brizard. Tested on GIMP-2.6
 Version 0.2: adapted to GIMP-2.8 (can no longer vary brush size with GIMP while...),
     introduce a configuration file, more differences between arrow type 0 and type 1,
     a notched arrow type and revised instructions at the window top.
 Versin 0.2.2 [2014/03/21]: armoring against missing element due to user, avoid
     duplicate plug-in launch and add to the configuration file.

================================================================================
 You may use and distribute this plug-in under the terms of the GPL 2 or greater.
"""

import gtk, pango, sys
import os, gettext
import pygtk
pygtk.require('2.0')
from gobject import timeout_add

try:
    from gimpfu import *
    from gimpshelf import shelf
except ImportError:
    print("Note: GIMP is needed, '%s' is a plug-in for it.\n"%fi)
    sys.exit(1)

### global variables ###########################################################

fi = __file__

# initialize internationalisation
locale_directory = os.path.join(os.path.dirname(os.path.abspath(fi)), 'locale')
gettext.install( "ArrowsCreator", locale_directory, unicode=True )

brush_name = ''
message = ''
# to detect if an arrow was drawn
arrow_done = False
# store the values of measuring arrow
measurements = []
# pointing with vectors
init_paths = []
ID_path = None
# timeout interval config?
Clock2 = []
inter_val = 0
# Start of arrow info
stub = _(u"Segment %d, arrow %d: ")
# to make it run for 2.6 and in 2.8
version = gimp.version
start_minver = 6 # minor version of the previous GIMP

#if version < (2, 6, 0) or version > (2, 8, 14) : 
    #print("Note: tested for 2.6 <= GIMP version <= 2.8 . Your is %s .\n"%str(version))

# for missing top layer (user error)
layer_miss = False

### GUI integration ############################################################

class ArrowWindow(gtk.Window):
    """
    The interactive interface to orchestrate this script
    """
    def __init__ (self, img, *args):
        self.img = img
        self.x1, self.y1, self.x2, self.y2 = 0, 0, 0, 0
        self.changed = False    # decides a redraw of the arrow
        self.miss = True        # to enconter only once a missing element

        self.headSize = 60     # side of the winghead in PX
        self.wingAngle = 25    # angle from arrow direction to the side in °
        self.brush = 11.0       # generated brush size

        self.choice_i = argmenu[2]  # index of arrow rendering choice
        if self.choice_i > 3 :      # style with circle choice
            self.slider3 = 50
            self.a3min = 0
            self.a3max = 200
        else :                      # style with gradient choice
            self.slider3 = 0        # value of third slider
            self.a3min = -25        # initial min limit for slider3
            self.a3max = +25        # initial max limit for slider3
            
        self.segment_cr = 1     # segment counter
        self.arrow_cr = 1       # arrow counter
        self.l_arrow = 0.1      # arrow length
        self.theta = 0          # arrow orientation angle in °
        self.direct = True      # arrow from first point to second if True

        # Make a new GIMP layer to draw on
        self.layer = gimp.Layer(img, _("AC_arrow #1"), img.width, img.height,
                                RGBA_IMAGE, 100, NORMAL_MODE)
        img.add_layer(self.layer, 0)
        # Verifies that it start at 1, not the case if we close and resume later
        if version[1] == start_minver : 
            name_layer = pdb.gimp_drawable_get_name(self.layer)
        elif version[1]  >  start_minver :
            name_layer = pdb.gimp_item_get_name(self.layer)
        if name_layer != _("AC_arrow #1") :
            ind_past = name_layer.find('#') + 1
            self.arrow_cr = int(name_layer[ind_past:])

        # Create the dialog
        win = gtk.Window.__init__(self, *args)
        self.set_title(_("Arrow tool for GIMP"))
        self.set_keep_above(True) # keep the window on top when it looses focus

        # The window manager quit signal:
        self.connect("destroy", gtk.main_quit)  

        # Make the UI
        self.set_border_width(10)
        vbox = gtk.VBox(spacing=6, homogeneous=False)
        self.add(vbox)
        title_line = _("Arrows creator  \n") 
        prompt_line = _("  To start: choose colours and path tool in design mode;")\
                +_("\nplace now two path anchors (nodes) by clicking at future")\
                +_("\narrow tail and head on the canvas (avoid closing the path).")\
                +_("\n An arrow should appear, then adjust values in this window.")\
                +_("\nIf not and you have followed the above, see end of status line.")\
                +_("\n You should move those anchors for the rest of the session.")\
                +_("\n To change the active arrow colour(s) and/or stroke path")\
                +_("\nafter it's drawn: change it in GIMP and a thing in the arrow.\n")
            # about 46 car. per line in 'label' 

        self.label = gtk.Label(title_line+prompt_line)

        # Change attributes of the label first line
        attr = pango.AttrList()
        fg_color = pango.AttrForeground(0, 0, 65535, 0, len(title_line))
        size = pango.AttrSize(17000, 0, 20)
        bold = pango.AttrWeight(pango.WEIGHT_ULTRABOLD, 0, len(title_line))
        attr.insert(fg_color)
        attr.insert(size)
        attr.insert(bold)
        self.label.set_attributes(attr)
        vbox.add(self.label)

        separator = gtk.HSeparator()
        vbox.pack_start(separator, expand=False)

        table = gtk.Table(rows=3, columns=2, homogeneous=False)
        table.set_col_spacings(10)
        vbox.add(table)

        # Arrowhead size
        label = gtk.Label(_("Arrowing size (PX)"))
        label.set_alignment(xalign=0.0, yalign=1.0)
        table.attach(label, 0, 1, 0, 1, xoptions=gtk.FILL, yoptions=0)
        adj = gtk.Adjustment(self.headSize, 0, 200, 1)
        adj.connect("value_changed", self.headsize_cb)
        scale = gtk.HScale(adj)
        scale.set_digits(0)
        scale.set_has_tooltip(True)
        scale.set_tooltip_text(_("arrow head side, 0 means no head"))
        table.attach(scale, 1, 2, 0, 1)

        # Arrowhead angle
        label = gtk.Label(_(u"Arrowing angle (°)"))
        label.set_alignment(xalign=0.0, yalign=1.0)
        table.attach(label, 0, 1, 1, 2, xoptions=gtk.FILL, yoptions=0)
        adj = gtk.Adjustment(self.wingAngle, 1, 80, 1)
        adj.connect("value_changed", self.headangle_cb)
        scale = gtk.HScale(adj)
        scale.set_digits(0)
        scale.set_has_tooltip(True)
        scale.set_tooltip_text(_("angle of a head wing in relation")\
                                +_("\nto head direction"))
        table.attach(scale, 1, 2, 1, 2)

        # Arrowshaft width
        label = gtk.Label(_("Brush size (radius,PX)\n for '%s'")%brush_name)
        label.set_alignment(xalign=0.0, yalign=1.0)
        table.attach(label, 0, 1, 2, 3, xoptions=gtk.FILL, yoptions=0)
        adj = gtk.Adjustment(self.brush, 1.0, 25, 2.0, 2.0)
        pdb.gimp_brush_set_radius(brush_name, self.brush)
        adj.connect("value_changed", self.brush_cb)
        scale = gtk.HScale(adj)
        scale.set_digits(0)
        scale.set_has_tooltip(True)
        scale.set_tooltip_text(_("for the plug-in generated brush,")\
                +_("\nit controls the shaft thickness."))
        table.attach(scale, 1, 2, 2, 3)
        
        # Fourth variable to be change by combo_box
        self.label3 = gtk.Label(_("Nr of gradient, shaft"))
        if version[1]  >  start_minver :
            self.label3.set_label(_("Gradient in shaft"))
        if self.choice_i > 3 : self.label3.set_label(_("Tail circle (radius,PX)"))
        self.label3.set_alignment(xalign=0.0, yalign=1.0)
        table.attach(self.label3, 0, 1, 3, 4, xoptions=gtk.FILL, yoptions=0)
        self.adj = gtk.Adjustment(self.slider3, self.a3min, self.a3max, 1)
        self.adj.connect("value_changed", self.slider3_cb)
        self.adj.connect("changed", self.slider3_lim)
        scale = gtk.HScale(self.adj)
        scale.set_digits(0)
        scale.set_has_tooltip(True)
        scale.set_tooltip_text(_("the adjustment purpose can change")\
                +_("\naccording to the arrow type"))
        table.attach(scale, 1, 2, 3, 4)

        table = gtk.Table(rows=1, columns=2, homogeneous=False)
        table.set_col_spacings(10)
        vbox.add(table)

        # Make a combo-box for options (independent choice for shaft and head?)
        choices = [_("Assegai style"),                       #0
                   _("Square cut the shaft"),                #1
                   _("Measuring arrow"),                     #2
                   _("Notched arrow"),                       #3
                  # from here third slider control the radius of a circle
                   _("Labelling arrow"),                     #4
                   _("Arrow with disk joint"),               #5
                   _("Arrow from the stroke path")]          #6
              # shaft only if choice is with head=0
        vbox2 = gtk.VBox(spacing=8)
        vbox2.set_border_width(10)
        vbox.pack_start(vbox2)
        combo_box = gtk.combo_box_new_text()
        combo_box.set_wrap_width(1)
        for i in range(len(choices)):
            combo_box.append_text("%d- %s" %(i,choices[i]))
        combo_box.set_active(self.choice_i)
        combo_box.set_has_tooltip(True)
        combo_box.set_tooltip_text(_("choice of arrow or segment type"))
        combo_box.connect("changed", self.choice_i_cb)
        table.attach(combo_box, 0, 1, 0, 1)

        rbtn = gtk.CheckButton(_("Invert"))
        rbtn.connect("toggled", self.direction_cb, None)
        rbtn.set_has_tooltip(True)
        rbtn.set_tooltip_text(_("inverse arrow direction"))
        table.attach(rbtn, 1, 2, 0, 1)

        separator = gtk.HSeparator()
        vbox.pack_start(separator, expand=False)

        # Show the actual arrow info
        self.states = [_("waiting for anchors           "), #0
                       _("edit"),                           #1
                       _("open the path (try Back-Space)"), #2
                       _("needs two anchors "),             #3
                       _("new localization"),               #4
                       _("anchor outside canvas!"),         #5
                       _("don't control that brush"),       #6
                       _("block by identical anchors"),     #7
                       _("completing the previous op."),    #8
                       _("won't work for that image!")]     #9
                       #"placer votre sélection"            
        arrow_label = stub%(self.segment_cr, self.arrow_cr) + self.states[0]
        l_label = len(arrow_label)
        attr1 = pango.AttrList()
        fg_color1 = pango.AttrForeground(30000, 20000, 0, 0, len(stub) -2)
        fg_color2 = pango.AttrForeground(0, 22000, 30000, len(stub) -2, l_label)
        size = pango.AttrSize(11500, 0, l_label)
        attr1.insert(fg_color1)
        attr1.insert(fg_color2)
        attr1.insert(size)

        self.label2 = gtk.Label(arrow_label)
        self.label2.set_alignment(0.0, 0.0)
        self.label2.set_attributes(attr1)
        self.label2.set_has_tooltip(True)
        self.label2.set_tooltip_text(_("info and state of current op"))
        vbox.add(self.label2)

        # Make the dialog buttons box
        separator = gtk.HSeparator()
        vbox.pack_start(separator, expand=False)
        hbox = gtk.HBox(spacing=20)

        btn = gtk.Button(_("Next segment"))
        btn.connect("pressed", self.next_seg)
        btn.set_has_tooltip(True)
        btn.set_tooltip_text(_("Mainly to produce a multi-segmented")\
                    +_("\nor many arrows on the previous layer"))
        hbox.add(btn)
        
        btn = gtk.Button(_("Next arrow"))
        btn.connect("pressed", self.next_arrow)
        btn.set_has_tooltip(True)
        btn.set_tooltip_text(_("Create a new arrow layer"))
        hbox.add(btn)
        
        self.btnc = gtk.Button(_("Close"))
        self.btnc.connect("pressed", self.press_close)
        hbox.add(self.btnc)

        vbox.add(hbox)
        self.show_all()
        
        self.update(*args)


    def press_close(self, data=None) :
        global measurements
        if arrow_done and self.choice_i == 2 :
            measurements.append((self.arrow_cr, self.segment_cr, self.l_arrow, \
                                 self.theta))
        if arrow_done and self.segment_cr > 1 :
            # check if there is an under layer and merge
            if len(self.img.layers) > 1 :
                self.img.raise_layer_to_top(self.layer)
                self.layer = self.img.merge_down(self.layer, 1)
            else : 
                self.terminate(_("layer to merge with"))
                return
        self.btnc.connect("released", gtk.main_quit)
        return

    def terminate(self, element) :
        # leave a message and terminate
        gimp.message(_("ERROR: a missing %s is undermining this plug-in")%element\
            +_(".\nIt has been auto terminated!"))
        # the update() function don't stop instantly it seems
        self.miss = False
        if gimp.image_list() == None : sys.exit(1)
        self.destroy()
        gtk.main_quit()
        return

    def direction_cb(self, rbtn, data=None) :
        if  self.choice_i == 2 : return
        if self.changed : return
        self.direct = not self.direct
        self.changed = True

    def headsize_cb(self, val) :
        if self.changed and arrow_done :
            # waiting on display the previous choice; more stable and less confusing?
            val.set_value(self.headSize)
            self.label2.set_label(stub%(self.segment_cr, self.arrow_cr) +\
                self.states[8])
            return
        self.headSize = val.value
        self.changed = True

    def headangle_cb(self, val) :
        if self.changed and arrow_done : 
            val.set_value(self.wingAngle)
            self.label2.set_label(stub%(self.segment_cr, self.arrow_cr) +\
                self.states[8])
            return
        self.wingAngle = val.value
        self.changed = True

    def brush_cb(self, val) :
        if pdb.gimp_context_get_brush() != brush_name :
            self.label2.set_label(stub%(self.segment_cr, self.arrow_cr) +\
                self.states[6])
            return
        if self.changed and arrow_done : 
            val.set_value(self.brush)
            self.label2.set_label(stub%(self.segment_cr, self.arrow_cr) +\
                self.states[8])
            return
        self.brush = val.value
        pdb.gimp_brush_set_radius(brush_name, self.brush)
        self.changed = True

    def slider3_cb(self, val) :
        if self.changed and arrow_done : 
            val.set_value(self.slider3)
            self.label2.set_label(stub%(self.segment_cr, self.arrow_cr) +\
                self.states[8])
            return
        self.slider3 = val.value
        self.changed = True

    def slider3_lim(self, adj) :
        adj.set_lower(self.a3min)
        adj.set_upper(self.a3max)
        adj.set_value(self.slider3)

    def choice_i_cb(self, combo_box) :
        if self.changed and arrow_done :
            combo_box.set_active(self.choice_i) 
            self.label2.set_label(stub%(self.segment_cr, self.arrow_cr) +\
                self.states[8])
            return
        # choose the appropiate slider3 for 'self.choice_1'
        previous = self.choice_i 
        self.choice_i = combo_box.get_active()
        to_grad = previous > 3 and self.choice_i < 4
        to_circ = previous < 4 and self.choice_i > 3
        if to_grad :
            if version[1]  ==  start_minver :
                self.label3.set_label(_("Nr of gradient, shaft"))
            else : self.label3.set_label(_("Gradient in shaft"))
            self.slider3 = 0
            self.a3min = -25
            self.a3max = 25
            self.adj.changed()            
        elif to_circ :
            self.label3.set_label(_("Tail circle (radius,PX)"))
            self.slider3 = 50
            self.a3min = 0
            self.a3max = 200
            self.adj.changed()
        self.changed = True
        
    def update(self, *args):
        # decides for updating the arrow
        
        global ID_path, Clock2, arrow_done, layer_miss

        timeout_add(inter_val, self.update, self)
        
        if self.miss :
            # check if image or layer or vector still there, if not exit plug-in
            if self.img not in gimp.image_list() :
                # not there, terminate           
                self.terminate(_("image"))
                return False
            layer_miss = self.layer not in self.img.layers
            # and self.layer.name == "segment"
            if layer_miss :
                self.terminate(_("layer at least"))
                return False        
            paths = self.img.vectors
            if arrow_done and ID_path not in paths :
                ID_path = None
                self.terminate(_("path at least"))
                return False

            try:
                points = paths[0].strokes[0].points
            except: return
        
            # 2 anchors with 2 handles each (6 coord. per anchor), points[0] stores
                # the coordinates, points[1] = True if the path is closed.
            nr_coord = len(points[0])
            if nr_coord != 12 or points[1] :
                # No 2 anchors or path close, no arrow
                if points[1] :
                    self.label2.set_label(stub%(self.segment_cr, self.arrow_cr) +\
                                          self.states[2])
                else :
                    self.label2.set_label(stub%(self.segment_cr, self.arrow_cr) +\
                                          self.states[3])
                self.changed = True
                return
            
            if ID_path == None: ID_path = paths[0]
            elif len(paths) > 1: points = ID_path.strokes[0].points
            # coordinates of first and next anchor
            lastX = nr_coord-4; lastY = nr_coord-3
            x1 = int(points[0][2]) ; x2 = int(points[0][lastX])
            y1 = int(points[0][3]) ; y2 = int(points[0][lastY])
            # check for identical anchors
            if x1 == x2 and  y1 == y2 :
                self.label2.set_label(stub%(self.segment_cr, self.arrow_cr) +\
                                 self.states[7])
                return
            # check if it's inside the image
            if  min(x1, y1, x2, y2) < 0 or max(x1, x2) > self.img.width or max(y1,\
                    y2) > self.img.height :
                self.label2.set_label(stub%(self.segment_cr, self.arrow_cr) +\
                                 self.states[5])
            
            if max(abs(self.x1-x1), abs(self.y1-y1), abs(self.x2-x2), abs(self.y2\
                    -y2)) < 2 and not self.changed :
                return
            
            # ID_path => tattoo?
            self.x1, self.y1, self.x2, self.y2 = x1, y1, x2, y2
            
            if version[1] < 8 : self.img.disable_undo()
            paths[0].visible = True

            # Clear the layer, erasing the old arrow
            self.layer.fill(TRANSPARENT_FILL)

            # Draw the new arrow from arrowhead to second X, Y pair.
            if self.direct : self.arrow_sel(x1, y1, x2, y2)
            else : self.arrow_sel(x2, y2, x1, y1)
            self.changed = False
            pdb.gimp_displays_flush()

            if version[1] < 8 : self.img.enable_undo()
            if not arrow_done : arrow_done = True
            return True
            
        else : return False     # if self.miss == False

    def arrow_sel(self, x1, y1, x2, y2) :
        """
         Computes common values for arrow and select 
         which function to call based on arrow type to draw it. 
        """ 
        # coords for arrowhead shape: 'points = []'
        # coords for arrow-shaft: strokes(start, end)
        strokes = [x1, y1, x2, y2]

        dy = y2 - y1
        dx = x2 - x1
        self.l_arrow = math.hypot(dx, dy)
        # arrowhead theoretical length (for the stroke path arrows)
        l_head_th = self.headSize * math.cos(self.wingAngle * math.pi / 180.)
        # computes values for direction
        theta = math.atan2(dy, dx)
        # it gives answer 0 to pi and 0 to -pi considering the signs of dy & dx
        self.theta = theta * 180 / math.pi  # for the user info

        # call one of straigth or path, def 'self.l_head', return 'points'
        if self.choice_i == 6 and l_head_th != 0 : points = self.head4path(x2, y2, l_head_th)
        else : points = self.head4staigth(x1, y1, x2, y2, theta)
        
        # if the 3 points are not colinear, then place a head
        head_bool = int(self.l_head) > 0 and  points[0][2:4] != points[0][4:6]
        # if swept wings head
        if self.choice_i == 3 :
            head_bool = head_bool and math.hypot(x2-points[0][4], y2-points[0][5])> 1.0
        # if straigth return 'strokes', for path dont need it
        strokes, ratio_ha = self.shaft_coord(dx, dy, strokes)

        # draw head(s) first--------------------
        if head_bool and self.choice_i == 0: self.m_head(points)
        
        # draw shaft  --------------------
        if ratio_ha < 1.0 or head_bool == False :
            # length of the gradient cycle wanted in 2.6, not in 2.8?
            four_var = 0
            slider3 = abs(self.slider3)
            if slider3 > 0 and self.choice_i < 4 :
                # four_var is cycl_grad a FLOAT
                if version[1]  ==  start_minver :
                    four_var = (self.l_arrow - self.l_head)/slider3
                else :
                    four_var = (self.l_arrow - self.l_head)/math.sqrt(slider3)
            elif self.choice_i == 4 :
                # four_var is fade            
                four_var = (self.l_arrow - self.l_head)*1.3     # fade is a FLOAT
            elif self.choice_i > 4 : 
                # four_var is radius
                if self.slider3 < int(self.l_arrow - self.l_head) : 
                    four_var = self.slider3
                #else : four_var = 0
            funct_dict = {0: self.d_shaft0, 1: self.d_shaft1, 2: self.d_shaft2,\
                          3: self.d_shaft3, 4: self.d_shaft4, 5: self.d_shaft5,\
                          6: self.d_shaft6}
            funct_dict.get(self.choice_i)(strokes, four_var)
            pdb.gimp_selection_none(self.img)

        # draw head(s) after--------------------
        if head_bool and self.choice_i: self.m_head(points)

        self.label2.set_label(stub%(self.segment_cr, self.arrow_cr)+\
            "%.1f px, %.1f°: %s"%(self.l_arrow, self.theta, self.states[1]))
        return

    def head4staigth(self, x1, y1, x2, y2, theta) :
        # computes coords of head apex for straight arrowhead
        points = []
        aangle = self.wingAngle * math.pi / 180.
        dxm = int(self.headSize * math.cos(theta - aangle))
        dym = int(self.headSize * math.sin(theta - aangle))
        dxp = int(self.headSize * math.cos(theta + aangle))
        dyp = int(self.headSize * math.sin(theta + aangle))
        points.append([ x2, y2,
                   x2 - dxm, y2 - dym,
                   x2 - dxp, y2 - dyp ])

        # actual length of triangular arrowhead in the shaft direction
        self.l_head = math.hypot(x2-(points[0][2] + points[0][4])/2.0 , y2-(\
                points[0][3] + points[0][5])/2.0)
        # 4 apex head, so add one apex on arrow line
        if self.choice_i == 0 or self.choice_i == 3 :
            if self.choice_i == 0 : shape = 1.5
            else :                  shape = 0.75
            dxa = int(self.l_head * shape * math.cos(theta))
            dya = int(self.l_head * shape * math.sin(theta))
            points = []
            points.append([ x2, y2,
                    x2 - dxm, y2 - dym,
                    x2 - dxa, y2 - dya,
                    x2 - dxp, y2 - dyp])
        # double triangular headed
        if self.choice_i == 2 :
            points.append([ x1, y1,
                       x1 + dxm, y1 + dym,
                       x1 + dxp, y1 + dyp ])
        return(points)

    def head4path(self, x2, y2, l_head_th) :
        # computes coords of arrowhead for path arrow
        points = []
        length = ID_path.strokes[0].get_length(3)
        factor = 1.0 + (length - self.l_arrow)/length
        for repeat in range(2) :
            if self.direct : dist = length - l_head_th*factor
            else : dist = l_head_th*factor
            x_point, y_point = ID_path.strokes[0].get_point_at_dist(dist, 2)[:2]
            l_head_new = math.hypot(x2-x_point, y2-y_point)
            if repeat == 0: factor += (l_head_th - l_head_new)/l_head_th
                
        # compute the 'points' for the head in that case
        width_arrow = l_head_new * math.tan(self.wingAngle * math.pi / 180.)
        deltaX = width_arrow*(y2-y_point)/l_head_new
        deltaY = width_arrow*(x2-x_point)/l_head_new
        points.append([ x2, y2,
                   round(x_point + deltaX), round(y_point - deltaY),
                   round(x_point - deltaX), round(y_point + deltaY) ])
        # actual length of arrowhead in the head direction
        self.l_head = math.hypot(x2-(points[0][2] + points[0][4])/2.0 , y2-\
                 (points[0][3] + points[0][5])/2.0)
        return(points)

    def shaft_coord(self, dx, dy, strokes) :
        # compute coords for arrowshaft
        # ratio is length_head/length_arrow, if >= 1 no shaft if there is a head
        ratio = self.l_head / self.l_arrow
        if self.choice_i != 6 :
            # don't go quite all the way to the end for self.choice_i != 3, 
            #   because of overshoot of shaft.
            if ratio != 0 and ratio < 1.0 :
                # a head at the end except for notched arrow where shaft is arrowlength
                if self.choice_i != 3 :
                    # from similar triangles
                    lcx = int(ratio*dx)
                    lcy = int(ratio*dy)
                    strokes[2] -= lcx
                    strokes[3] -= lcy
                # a head at the beginning
                if self.choice_i == 2 :
                    strokes[0] += lcx
                    strokes[1] += lcy
                    ratio *= 2.0
            # next is independant of arrow head size
            if self.slider3 < 0 and ratio < 1.0 : 
                    # inverse gradient: pdb.gimp_context_swap_colors(), not as general?
                    strokes = [strokes[2], strokes[3], strokes[0], strokes[1]]
            else : strokes = [strokes[0], strokes[1], strokes[2], strokes[3]] 
        return(strokes, ratio)
    
    def d_shaft0(self, strokes, cycl_grad) :
        # Arrow shaft is a paintbrush stroke after the head
        pdb.gimp_paintbrush(self.layer, 0.0, 4, strokes, 0, cycl_grad)
        # put a rivet for fixation at shaft-head
        br_radius = pdb.gimp_brush_get_radius(brush_name)
        pdb.gimp_brush_set_radius(brush_name, self.brush/3.0)
        if self.slider3 >= 0 : riv_pt = [strokes[2], strokes[3]]
        else : riv_pt = [strokes[0], strokes[1]]
        pdb.gimp_paintbrush_default(self.layer, 2, riv_pt)
        pdb.gimp_brush_set_radius(brush_name, br_radius)
        return

    def d_shaft1(self, strokes, cycl_grad) :
        # a selection to square cut the following 'paintbrush' operation
        width_sel = self.brush
        deltaX = round(width_sel*(self.y2-self.y1)/self.l_arrow)
        deltaY = round(width_sel*(self.x2-self.x1)/self.l_arrow)
        points_shaft = [strokes[2]+deltaX , strokes[3]-deltaY,\
                        strokes[2]-deltaX , strokes[3]+deltaY,\
                        strokes[0]-deltaX, strokes[1]+deltaY,\
                        strokes[0]+deltaX, strokes[1]-deltaY ]
        if version[1] == start_minver :
            pdb.gimp_free_select(self.img, 8,\
                points_shaft, CHANNEL_OP_REPLACE, True, False, 0)
        elif version[1]  >  start_minver :
            pdb.gimp_image_select_polygon(\
                self.img, CHANNEL_OP_REPLACE, 8, points_shaft)
        pdb.gimp_paintbrush(self.layer, 0.0, 4, strokes, 0, cycl_grad)
        return

    def d_shaft2(self, strokes, cycl_grad) :
        # measuring arrow: X width of shaft, double heads
        fX = (self.y2- self.y1)/self.l_arrow
        fY = (self.x2- self.x1)/self.l_arrow
        #width_sel = self.headSize*math.sin(self.wingAngle*math.pi/180.) + 1
        # no head above don't produce a shaft so base it on shaft width
        width_sel = self.brush*1.5
        deltaX = round(width_sel*fX)
        deltaY = round(width_sel*fY)
        points_shaft = [strokes[2]+deltaX , strokes[3]-deltaY,
                        strokes[2]-deltaX , strokes[3]+deltaY,
                        # make an X shaft!
                        strokes[0]+deltaX, strokes[1]-deltaY,
                        strokes[0]-deltaX, strokes[1]+deltaY ]
        # for the arrow centre symmetry: two paint-brush strokes
        x_center = (strokes[0]+strokes[2])/2.0
        y_center = (strokes[1]+strokes[3])/2.0
        # to inverse the gradient
        if self.slider3 > 0 :
            half_stroke1 = [x_center, y_center, strokes[0], strokes[1]]
            half_stroke2 = [x_center, y_center, strokes[2], strokes[3]]
        else :
            half_stroke1 = [strokes[0], strokes[1], x_center, y_center]
            half_stroke2 = [strokes[2], strokes[3], x_center, y_center]
        # X shaft by that selection
        if version[1] == start_minver : 
            pdb.gimp_free_select(self.img, 8, points_shaft, \
                CHANNEL_OP_REPLACE, True, False, 0)
        elif version[1]  >  start_minver :
            pdb.gimp_image_select_polygon(self.img,\
                CHANNEL_OP_REPLACE, 8, points_shaft)

        pdb.gimp_paintbrush(self.layer, 0.0, 4, half_stroke1, 0, cycl_grad)
        pdb.gimp_paintbrush(self.layer, 0.0, 4, half_stroke2, 0, cycl_grad)
        
        return
        
    def d_shaft3(self, strokes, cycl_grad) :
        # a selection for notched arrow
        width_sel = self.brush
        
        if self.slider3 < 0 : 
            strokes = [strokes[2], strokes[3], strokes[0], strokes[1]]
        deltaX = round(width_sel*(strokes[3]-strokes[1])/self.l_arrow)
        deltaY = round(width_sel*(strokes[2]-strokes[0])/self.l_arrow)
        points_shaft = [strokes[2] , strokes[3],\
                        strokes[0]-deltaX, strokes[1]+deltaY,\
                        strokes[0]+deltaY*0.7, strokes[1]+deltaX*0.7,\
                        strokes[0]+deltaX, strokes[1]-deltaY ]

        if version[1] == start_minver :
            pdb.gimp_free_select(self.img, 8,\
                points_shaft, CHANNEL_OP_REPLACE, True, False, 0)
        elif version[1]  >  start_minver :
            pdb.gimp_image_select_polygon(\
                self.img, CHANNEL_OP_REPLACE, 8, points_shaft)
        if self.slider3 < 0 : 
            strokes = [strokes[2], strokes[3], strokes[0], strokes[1]]
        pdb.gimp_paintbrush(self.layer, 0.0, 4, strokes,\
            0, cycl_grad)
        return

    def d_shaft4(self, strokes, fade) :
        # labelling arrow
        short_shaft = self.l_arrow - self.l_head
        if self.slider3 < short_shaft : radius = self.slider3
        elif self.slider3 < 3 :  radius = 0
        else :  radius = int(short_shaft)
        if radius :
            # disk selection and stroke circle
            px = strokes[0] - radius
            py = strokes[1] - radius
            sign = 1
            if not self.direct : sign = -1
            strokes[0] += round(radius*(self.x2-self.x1)*sign/self.l_arrow)
            strokes[1] += round(radius*(self.y2-self.y1)*sign/self.l_arrow)
            if version[1] == start_minver : 
                pdb.gimp_ellipse_select(self.img, px, py,\
                   2*radius, 2*radius, CHANNEL_OP_REPLACE, True, False, 0)
            elif version[1]  >  start_minver : 
                pdb.gimp_image_select_ellipse(self.img, CHANNEL_OP_REPLACE,\
                   px, py, 2*radius, 2*radius)
            br_radius = pdb.gimp_brush_get_radius(brush_name)
            pdb.gimp_brush_set_radius(brush_name, 1.5)
            pdb.gimp_edit_stroke(self.layer)
            pdb.gimp_brush_set_radius(brush_name, br_radius)

            pdb.gimp_selection_none(self.img)
        # put a mark at the circle centre if no radius
        else : pdb.gimp_paintbrush(self.layer, 0.0, 2, strokes[:2], 0, 0.0)

        # inverse stroke to have stronger color at head for 2.6
        if version[1] == start_minver :
            strokes = [strokes[2], strokes[3], strokes[0], strokes[1]]
        # do nothing for 2.8
        pdb.gimp_paintbrush(self.layer, fade, 4, strokes, 0, 0.0)
        return

    def d_shaft5(self, strokes, radius) :
        # disk joint arrow
        cycl_grad = self.l_arrow - self.l_head  #cycl_grad is a FLOAT
        #cycl_grad = 0
        pdb.gimp_paintbrush(self.layer, 0.0, 4, [strokes[2], strokes[3], strokes[0],\
            strokes[1]], 0,  cycl_grad)
        if radius :
            px = strokes[0] - radius
            py = strokes[1] - radius
            if version[1] == start_minver : 
                pdb.gimp_ellipse_select(self.img, px, py, 2 * radius,\
                    2 * radius, CHANNEL_OP_REPLACE, True, False, 0)
            elif version[1] > start_minver :
                pdb.gimp_image_select_ellipse(self.img, CHANNEL_OP_REPLACE,\
                    px, py, 2 * radius, 2 * radius)
            pdb.gimp_edit_fill(self.layer, BACKGROUND_FILL)
            pdb.gimp_selection_none(self.img)
        return

    def d_shaft6(self, strokes, radius) :
        # Stroke the path
        if radius :
            # draw the starting disk
            px = strokes[0]-radius
            py = strokes[1]-radius
            if version[1] == start_minver : 
                pdb.gimp_ellipse_select(self.img, px, py, 2.0*radius, \
                    2.0*radius, CHANNEL_OP_REPLACE, True, False, 0)
            elif version[1]  >  start_minver : 
                pdb.gimp_image_select_ellipse(self.img, CHANNEL_OP_REPLACE,\
                    px, py, 2.0*radius, 2.0*radius)
            pdb.gimp_edit_fill(self.layer, FOREGROUND_FILL)
            pdb.gimp_selection_none(self.img)
        OP_type = CHANNEL_OP_REPLACE
        if self.l_head > 0 :
            # make a selection to stop the stroke at the arrow head
            x_head = strokes[2] - int(self.l_head)
            y_head = strokes[3] - int(self.l_head)
            if version[1] == start_minver : 
                pdb.gimp_ellipse_select(self.img, x_head, y_head,\
                    int(2*self.l_head)-1, int(2*self.l_head)-1, OP_type, True,\
                    False, 0)
            elif version[1]  >  start_minver : 
                pdb.gimp_image_select_ellipse(self.img, OP_type,\
                    x_head, y_head, int(2*self.l_head)-1, int(2*self.l_head)-1)

            pdb.gimp_selection_invert(self.img)
            
        pdb.gimp_edit_stroke_vectors(self.layer, ID_path)
        return

    def m_head(self, points) :
        """
         Select and paint the arrowhead shape(s) (or other decorations?) 
         'points' is in the form [[6 coords], [6 coords], ...] for triangles
        """ 
        # Select the arrowhead shape(s)
        for h in points:
            if version[1] == start_minver : 
                pdb.gimp_free_select(self.img, len(h), h, CHANNEL_OP_ADD, True,\
                                                         False, 0)
            elif version[1]  >  start_minver : 
                pdb.gimp_image_select_polygon(self.img, CHANNEL_OP_ADD, \
                                                         len(h), h)
                            
        # Fill the arrowhead(s), PATTERN_FILL work too
        pdb.gimp_edit_fill(self.layer, FOREGROUND_FILL)
        pdb.gimp_selection_none(self.img)
        return

    def next_seg(self, btn, data=None) :
        global arrow_done, measurements
        if arrow_done :
            if self.segment_cr > 1 :
                # check if there is an under layer and merge
                if len(self.img.layers) > 1 :
                    self.img.raise_layer_to_top(self.layer)
                    layer = self.img.merge_down(self.layer, 1)
                else : self.terminate(_("layer to merge with"))
            self.layer = gimp.Layer(self.img, "AC_segment", self.img.width, \
                self.img.height, RGBA_IMAGE, 100, NORMAL_MODE)
            self.img.add_layer(self.layer, 0)
            if self.choice_i == 2 :
                measurements.append((self.arrow_cr, self.segment_cr, \
                                     self.l_arrow, self.theta))
            self.segment_cr += 1
            self.direct = not self.direct
            # Indicate segment mode in the info line by a number > 1
            self.label2.set_label(stub%(self.segment_cr, self.arrow_cr) + \
                                  self.states[4])
            prompt_line = _("  Next segment: click on the first anchor of the")\
                    +_("\npreceding segment (tail) and drag it where you want")\
                    +_("\nthe new head to be, for consecutive segments.")\
                    +_("\nThe GIMP grid could be helpful to align many segments.")\
                    +_("\n\n  N.B.: to produce a curve path 'click+drag' when placing ")\
                    +_("\nan anchor or/and on the path after.")\
                    +_("\n  Warning: keep initial image, don't change path layer or ")\
                    +_("\nremove top arrow or segment layer while the plug-in is active.\n")
            self.label.set_label(_("Arrows creator  \n") + prompt_line)
            arrow_done = False
        else : mssgBox(mess)

    def next_arrow(self, data=None):
        global arrow_done, measurements

        # Make a new GIMP layer to draw on if ...
        if self.segment_cr > 1 and not arrow_done : arrow_done = True
        
        if arrow_done :
            if self.choice_i == 2 :
                measurements.append((self.arrow_cr, self.segment_cr, \
                                     self.l_arrow, self.theta))
            if self.segment_cr > 1 :
                # check if there is an under layer and merge
                if len(self.img.layers) > 1 : 
                    self.img.raise_layer_to_top(self.layer)
                    layer = self.img.merge_down(self.layer, 1)
                else : self.terminate(_("layer to merge with"))
                if not self.segment_cr%2 : self.direct = not self.direct
                self.segment_cr = 1
            self.arrow_cr += 1
            self.label2.set_label(stub%(self.segment_cr, self.arrow_cr) + \
                                  self.states[4])
            self.layer = gimp.Layer(self.img, _("AC_arrow #")+str(self.arrow_cr),\
                self.img.width, self.img.height, RGBA_IMAGE, 100, NORMAL_MODE)
            self.img.add_layer(self.layer, 0)
            pdb.gimp_displays_flush()
            prompt_line = _("  Next arrow: click on the anchors and drag them")\
                +_("\nto the desired places. If you mistakenly create a new")\
                +_("\nanchor, erase it with 'Back Space'.")\
                +_("\n  To have two anchors selected: 'Shift+click' on the one not")\
                +_("\nselected (solid dot one) or click on the path, this permits a")\
                +_("\ntranslation movement when you drag one anchor. One exits ")\
                +_("\nthis state by 'Shift+click' on an anchor.\n")
            self.label.set_label(_("Arrows creator  \n")+prompt_line)
            arrow_done = False
        # No previous arrow done. Popup a message
        else : mssgBox(mess)

mess = _("   Message from ArrowsCreator:")\
      +_("\nGoes to the next step only if the current layer is not")\
      +_("\nempty. Empty layer wastes a lot of memory.")\
      +_("\nSo put an arrow (segment) in or 'close'.")

def mssgBox(mess):
    flag = gtk.DIALOG_MODAL|gtk.DIALOG_DESTROY_WITH_PARENT
    msgBox = gtk.MessageDialog(None, flag, gtk.MESSAGE_WARNING, gtk.BUTTONS_OK,\
    mess)
    msgBox.run()
    msgBox.destroy()

### Main procedure #############################################################
            
def arrows_creator(image, layer):
    global arrow_done, init_paths, ID_path, inter_val, brush_name

    if message: gimp.message(message)
    wdth = image.width
    hght = image.height

    # with gimpshelf avoid duplicate launch
    if shelf.has_key('arrows_creator') and shelf['arrows_creator']:
        gimp.message(_("ERROR: an 'arrows creator' instance is already running!"))
    else:

        #1) Preparations
        # ********************************************
        shelf['arrows_creator'] = True

        # instability of GIMP-2.6 core with 'image.undo_group' here but work in 2.8
        if version[1] > 7 : image.disable_undo()
        # initial paths?
        init_paths = image.vectors
        if init_paths: 
            for p in init_paths : p.visible = False
            # before putting two anchors, case when called from tracing a path
            vectors_new = pdb.gimp_vectors_new(image, _("AC buffer"))
            pdb.gimp_image_add_vectors(image, vectors_new, -1)

        # configure time interval in timeout_add(), probably depends on image size &
            # sluggishness? Greater interval: more time for GIMP? Approximation.
        slug = 1.0 # Linux 64 bits, 4 cores at 2.83 GHz, GIMP 2.6.11 (64 b)
        #slug = 1.4 # Win_7 64 bits, 8 cores at 2 GHz, GIMP 2.6.11 (32 b)
        inter_val = int((0.26*math.sqrt(wdth*hght) + 100)*slug)
        
        # generated brush
        previous_brush = pdb.gimp_context_get_brush()
        #brush_name = pdb.gimp_brush_duplicate(bru_con_nam) #next line gives less surprise
        brush_name = pdb.gimp_brush_new('AC_brush')
        pdb.gimp_brush_set_shape(brush_name, 0)
        pdb.gimp_brush_set_hardness(brush_name, 1.0)
        pdb.gimp_context_set_brush(brush_name)
        if version[1]  >  start_minver: pdb.gimp_context_set_dynamics("Dynamics Off")
        

        #2) Main event    
        # ********************************************
        r = ArrowWindow(image)
        gtk.main()

        #3) Closing
        # ********************************************
        # cleanup brush
        pdb.gimp_context_set_brush(previous_brush)
        pdb.gimp_brush_delete(brush_name)

        if image in gimp.image_list():
            # cleanup path
            if ID_path:
                pdb.gimp_image_remove_vectors(image, ID_path)
            if init_paths and ID_path != vectors_new : 
                pdb.gimp_image_remove_vectors(image, vectors_new)
            #pdb.gimp_item_set_tattoo(item, tattoo)
        
            # cleanup layer, if close before the arrow is drawn
            if not arrow_done and not layer_miss :   # and no missing top layer
                #item = pdb.gimp_image_get_active_layer(image)
                image.remove_layer(image.layers[0])

            if version[1] > 7 : image.enable_undo()
            # permitting the user to keep tab on measuring arrow
            if measurements :
                if gimp.version >= (2, 8, 0):
                    temp_name = str(image.filename)
                    if temp_name:
                        start_tmp = temp_name.rfind(os.sep)+1
                        end_tmp = temp_name.find('.', start_tmp)
                        if end_tmp > 0:
                            cur_name = temp_name[start_tmp:end_tmp]
                        else: cur_name = temp_name[start_tmp:]
                    else: cur_name = curImages[id].name[:curImages[id].name.find('.')]
                # this was working in 2.6
                else: cur_name = image.name

                mess_txt = _("MEASURING ARROW in %s: \n\n Nr    Size")%cur_name\
                        +_("    Direction (clockwise +)\n")
                for arrow in measurements :
                    mess_txt += "  %s  %.1f px \t %.1f°\n"%(str(arrow[0])+'.'+\
                                        str(arrow[1]), arrow[2], arrow[3])
                gimp.message(mess_txt)

        shelf['arrows_creator'] = False

### Choosing menu path #########################################################

sep = os.sep
sys_encoding = sys.getfilesystemencoding()
argmenu = ''

def sys_file(f_name):
    if os.name == 'nt': encoded = f_name.encode(sys_encoding)
    else: encoded = f_name
    return(encoded)

class MenuArrowsCreator(gtk.Window):
    """ Plug-in configuration: menu and default value """
    
    def __init__ (self):
        gtk.Window.__init__(self)
        self.set_title(_("ArrowsCreator configuration"))
        #self.set_urgency_hint(True) # worse than before
        # The window manager quit signal:
        self.connect("destroy", gtk.main_quit)  
    
        # Make the UI
        self.set_border_width(10)
        vbox = gtk.VBox(spacing=6, homogeneous=True)
        self.add(vbox)
        prompt_line = _("  To simplify the menu placement on the image menu-bar ")\
            +_("where\nwe want it, It produces a file, after this it will no ")\
            +_("longer appear unless\nyou erase '%s'.")%file_shelf
    
        self.label = gtk.Label(prompt_line)
        vbox.add(self.label)

        separator = gtk.HSeparator()
        vbox.pack_start(separator, expand=False)

        # rows number in the following table depends of the return dict.
        table = gtk.Table(rows=3, columns=2, homogeneous=False)
        table.set_col_spacings(10)
        vbox.add(table)

        # menu path entry
        label = gtk.Label(_("menu path = <image>"))
        label.set_alignment(xalign=0.0, yalign=1.0)
        table.attach(label, 0, 1, 0, 1, xoptions=gtk.FILL, yoptions=0)
        # text entry 'gtk.Entry(max=0)'
        self.entry = gtk.Entry(max=100)
        self.entry.set_text(argmenu[1])
        self.entry.set_has_tooltip(True)
        self.entry.set_tooltip_text(_(" Edit this partial menu path to your liking")\
            +_(".\nIf plug-in was registered before,")\
        +_(" change will take place, for example, after a 'touch' to %s")%fi)
        table.attach(self.entry, 1, 2, 0, 1)

        label = gtk.Label(_("plug-in name = "))
        label.set_alignment(xalign=0.0, yalign=1.0)
        table.attach(label, 0, 1, 1, 2, xoptions=gtk.FILL, yoptions=0)
        self.entry1 = gtk.Entry(max=100)
        self.entry1.set_text(argmenu[0])
        self.entry1.set_has_tooltip(True)
        self.entry1.set_tooltip_text(_(" Change or/and choose an accelerator ")\
            +_("key by inserting one or \ndisplacing an '_' before the accelerated letter."))
        table.attach(self.entry1, 1, 2, 1, 2)

        # arrow style default here
        label = gtk.Label(_("default arrow style number = "))
        label.set_alignment(xalign=0.0, yalign=1.0)
        table.attach(label, 0, 1, 2, 3, xoptions=gtk.FILL, yoptions=0)
        value = gtk.Adjustment(0, 0, 6, 1)
        self.style_init = gtk.SpinButton(value)
        self.style_init.set_value(argmenu[2])
        self.style_init.set_has_tooltip(True)
        self.style_init.set_tooltip_text(_(" Choose the beginning arrow style."))
        table.attach(self.style_init, 1, 2, 2, 3, xoptions=gtk.FILL, yoptions=0)
        
        separator = gtk.HSeparator()
        vbox.pack_start(separator, expand=False)

        hbox = gtk.HBox(spacing=5)
        self.btnc = gtk.Button(_("OK"))
        self.btnc.set_has_tooltip(True)
        self.btnc.set_tooltip_text(_("If instead this window is cancel with [x] the")\
            +_(" default will be used."))
        self.btnc.connect("pressed", self.press_ok)
        hbox.add(self.btnc)

        vbox.add(hbox)
        self.show_all()

        return

    def press_ok(self, data=None) :
        global argmenu, plugin_name
        argmenu = [self.entry1.get_text(), self.entry.get_text(), \
            int(self.style_init.get_value())]
        self.btnc.connect("released", gtk.main_quit)
        self.destroy()

# folder name to save the configuration is the same as the plug-in file
fold_name = fi[fi.rfind(sep)+1:fi.rfind('.')]
# next is the starting name, menu_path and values of arrow style default
argmenu = [_("Arrows crea_tor..."), _("/Extensions/Plugins-Python/Tools"), 0]

# config values from data file
folder = os.path.dirname(os.path.abspath(fi))+sep+fold_name
# if folder not there, create it
folder = sys_file(folder)   #sys_file() for Windows
if not os.path.exists(folder): os.mkdir(folder)
file_shelf = sys_file(folder+sep+'menu_path')
if os.path.isfile(file_shelf):
    data = open(file_shelf, 'r')
    argmenu = eval(data.read())
    if len(argmenu) == 2: argmenu.append(0)
    data.close()

# no 'menu_path' file, configure 'argmenu' and save
else: 

    # next is the UI for the user menu-path input
    MenuArrowsCreator()
    gtk.main()

    # write in ArrowsCreator data file
    f = open(file_shelf, 'w')
    f.write(repr(argmenu))
    f.close()

### End choosing menu path #####################################################
        
register(
         "arrows_creator",  # proc-def in pluginrc
         _("Draw interactive arrows based on a path with two anchors.")\
             +_( "\nFrom: ")+fi,
         "Draw an arrow following the current path anchors, updating as the "\
             +"anchor changes position.",
         "Akkana Peck, R. Brizard",
         "(c) Robert Brizard",
         "2011",
         argmenu[0],                    #"Arrows crea_tor...",
         "*",
         [
          (PF_IMAGE, "image", "IMAGE:", None),
          (PF_DRAWABLE, "layer", "DRAWABLE:", None)
          
         ],
         [],
         arrows_creator,
         menu = "<Image>"+argmenu[1],   #"/Extensions/Plugins-Python/Tools"
         domain=( "ArrowsCreator", locale_directory)
        )

main()
