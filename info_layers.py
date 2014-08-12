#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
# (c) 2012 by David Maquez de la Cruz (at http://registry.gimp.org/node/26317)
# TODO: Check if it's possible to show info because sometimes
# there is an error into the error console, i.e when there is no layer
 June 2014, by Robert Brizard:
   seems based on 'ratio_info.py' from Joao S. Bueno in 2007,
   the additions are: 
    1) adding text explanations (date, etc...), about the layer, in a layer parasite;
    2) plug-in auto quit if no layer or initial image;
    3) permitting internationalization in 'user' folders;
    4) only one launch at a time;
    5) save the info for all layers in a text file.
 August 2014 version 0.1:
    1) an alternate way to select the active layer;
    2) display two others properties: position and type.

   Make sense, fully, for 'XCF' file.
================================================================================
 You may use and distribute this plug-in under the terms of the GPL 2 or greater.
 Get the license text at "http://www.gnu.org/licenses/" 
"""

import gtk, glob, pango
import os, gettext
from gobject import timeout_add
#from collections import namedtuple

try:
    from gimpfu import *
    from gimpshelf import shelf
except ImportError:
    print("Note: GIMP is needed, '%s' is a plug-in for it.\n"%__file__)
    sys.exit(1)

### global variables ###########################################################

fi = __file__

# initialize internationalization in a user-locale
locale_directory = os.path.join(os.path.dirname(os.path.abspath(fi)), 'locale')
gettext.install( "info_layers", locale_directory, unicode=True )

stop = False
prob = _("\nProblem probably with the starting image!\n  Plug-in has auto quitted.")
enum_type = [_('RGB'), _('RGBA'), _('GRAY'), _('GRAYA'), _('INDEXED'), _('INDEXEDA')]
version = gimp.version
start_minver = 6 # minor version of the previous GIMP-2.6

### GUI integration ############################################################

class LayerInfo(gtk.Window):
    def __init__ (self, img, drw, *args):
        self.img = img
        self.drw = drw
        self.text = None
        self.layers = []        # layers object list for the image
        self.pre_save = []    # previous names list for 'Save all' label
        self.names = []
        self.pre_names = []
        self.flag_paras = False # track 'Enter text' after a 'Save all'
        self.flag_save = False  # track 'Save all (done)'
        self.w, self.h = 0, 0
        self.pos, self.pre_max_pos = 0, 0
        
        r =  gtk.Window.__init__(self, *args)
        # The window manager quit signal:
        self.connect("destroy", gtk.main_quit)  

        self.set_title(_("INFO on active layer"))

        vbox = gtk.VBox(spacing=6, homogeneous=False)
        # special line for name of layer choice
        self.combo_box = gtk.combo_box_new_text() #gtk.ComboBox()
        self.combo_box.set_wrap_width(1)
        self.combo_box.set_has_tooltip(True)
        self.combo_box.set_tooltip_text(_("Choice of active layer by a click and\n")\
            +_("selection here or in GIMP layer dialog."))
        self.combo_box.connect("changed", self.name_change)
        vbox.add(self.combo_box)

        # info under layer name
        self.label = gtk.Label()
        self.label.set_has_tooltip(True)
        self.label.set_tooltip_text(_("Position: on the layer stack from the top.")\
            +_("\nType: Single or Group and the base channels.\n")\
            +_("Parasite: gives the number of layer parasite(s) attached\n")\
            +_("and if 'layer-info' is one or not."))
        vbox.add(self.label)

        separator = gtk.HSeparator()
        vbox.add(separator)

        # for viewing or adding explanations, in a parasite

        hbox = gtk.HBox(False, 0)
        # label for the managed parasite 
        self.label1 = gtk.Label()
        self.label1.set_use_markup(True)
        self.label1.set_has_tooltip(True)
        self.label1.set_tooltip_text(_("Name of the layer parasite managed by this plug-in.\n")\
            +_("If in blue: next field is the layer parasite text content or none.\n")\
            +_("If in red: an edited text not attached yet."))
        hbox.add(self.label1)

        # text in or should be in the managed parasite
        self.entry = gtk.Entry(max=0)
        self.entry.set_has_tooltip(True)
        self.entry.set_tooltip_text(_("Display text for layer parasite: 'layer-info'.\n")\
            +_("It permits editing or creating that parasite."))
        hbox.add(self.entry)
        vbox.add(hbox)

        # add action buttons
        hbox = gtk.HBox(homogeneous=False, spacing=6)
        btn = gtk.Button(_("Enter text"))
        btn.connect("pressed", self.add_info)
        btn.set_has_tooltip(True)
        btn.set_tooltip_text(_("Enter preceding text in layer parasite: 'layer-info'.")\
            +_("\nN.B.: a layer parasite is kept only in 'XCF' file."))
        hbox.add(btn)

        self.btn = gtk.Button(_("Save all"))
        self.btn.connect("pressed", self.save_file)
        self.btn.set_has_tooltip(True)
        self.btn.set_tooltip_text(_("Save the info for all layers in a text file."))
        hbox.add(self.btn)
        vbox.add(hbox)

        # completes this window
        self.add(vbox)
        self.show_all()
        self.set_keep_above(True)
        timeout_add(200, self.update, self)
        return r

    def update(self, *args):
        """ update the info in the GUI """

        global stop, prob

        img_list = gimp.image_list()
        if (self.img not in img_list) or (len(self.img.layers) == 0) or stop:
            gimp.message(prob+_("\nIn update() first 'if' case"))
            stop = True
            gtk.main_quit()
            return False
        # change during the execution? Next to force auto quitting
        try:
            # Choose an active layer by plugin? self.img.active_layer = ?
            self.drw = self.img.active_layer
            #> layer name
            self.layers = get_all_layers(self.img)
            self.names = [lay.name.replace("\n", "/").replace("'", "\'") for lay in self.layers]
            name = self.names[self.layers.index(self.drw)]
            #> layer offsets
            x, y = pdb.gimp_drawable_offsets(self.drw)
            #> layer position on the stack
            self.pos = self.layers.index(self.drw) +1
            max_pos = len(self.layers)
            #> layer size
            h = pdb.gimp_drawable_height(self.drw)
            w = pdb.gimp_drawable_width(self.drw)
            #> layer type
            _type = pdb.gimp_drawable_type(self.drw)
            # Group or Single + ?
            if hasattr(self.drw,"layers"): Type = _("Group, ")+enum_type[_type]
            else: 
                if pdb.gimp_drawable_is_text_layer(self.drw):
                    Type = _("Single text, ")+enum_type[_type]
                else: Type = _("Single, ")+enum_type[_type]
            #> layer parasite
            n, parasites = get_parasite_list(self.drw)
            nflag = parasites.count('layer-info')
            if  nflag == 0:
                paras_text = ''
                flag = _('no')
            else:
                paras_text = str(self.drw.parasite_find('layer-info'))
                # seems that parasite add a zero byte at the end which don't agree with 'gtk.label'
                paras_text = paras_text.strip(chr(0))
                flag = _("yes") # put parasite text in the entry field
        except: 
            gimp.message(prob+_("\nIn update() 'except' case"))
            stop = True
            gtk.main_quit()
            return False

        if not stop: timeout_add(200, self.update, self)

        # packing the layer info into text
        txt = _("    Position : %d of %d  \n    Type : %s  \n    Name : %s ")\
            % (self.pos, max_pos, Type, name)\
            +_("\n    Offsets(x,y) : (%d , %d) px    \n    Size(W,H) : %dx%d px  \n    Parasite : %d , %s")\
            % (x, y, w , h, n, flag)

        # update() in two parts:
        # 1) the same text in the info list
        if self.text == txt:

            # change colour of 'layer-info:' if new entry text
            entry_txt = self.entry.get_text()
            if entry_txt != paras_text:
                self.label1.set_label("<span foreground='dark red' background='white' >"+\
                    " layer-info: "+"</span>")
                self.label1.set_use_markup(True)
            else:
                self.label1.set_label("<span foreground='blue' background='white' >"+\
                    ' layer-info: '+"</span>")
                self.label1.set_use_markup(True)

            # reset label on 'Save' button after a save if there some change
            if self.flag_save and (self.pre_save != self.names or self.flag_paras):
                self.btn.set_label(_("Save all"))
                self.pre_save = self.names
                self.flag_save = False
            return

        # 2) different text, displays it in the window...
        self.label.set_label(txt)

        # the parasite content
        if  nflag != 0: 
            self.entry.set_text(paras_text)
        else: 
            self.entry.set_text('')

        # updating the combo_box?
        if self.pre_names != self.names:
            # empty self.combo_box; next seems to work
            for i in range(self.pre_max_pos): self.combo_box.remove_text(0)
            # repopulate it
            for nam in self.names: self.combo_box.append_text("   %s" %nam)
            self.pre_max_pos = len(self.names)
            self.pre_names = self.names
        self.combo_box.set_active(self.pos-1)

        self.text = txt
        return True

    def name_change(self, btn, data=None) :
        pdb.gimp_image_set_active_layer(self.img, self.layers[btn.get_active()])
        pdb.gimp_displays_flush()
        return

    def add_info(self, btn, data=None) :
        paras_text = self.entry.get_text()
        self.drw.attach_new_parasite('layer-info', 1, paras_text)
        # to indicate a save text in the parasite
        self.label1.set_label("<span foreground='blue' background='white' >"+\
            ' layer-info: '+"</span>")
        self.label1.set_use_markup(True)
        # flag to indicate usage of this
        if self.flag_save: self.flag_paras = True
        else: self.flag_paras = False
        return
        
    def save_file(self, btn, data=None) :
        """ 
        Create a text file with the info for all layers and their parasites
        """
        
        # for a XML file see  'Python-Fu #3 - Working with Layers and XML in Python-Fu'
        filename = ""
        tags = (_(') Group '), _(') Single '))

        btn.set_label(_("Save all"))    # to reflect prob. if saving more than once
        # start building our text file first by an introduction
        txt = _("# An info layers file for '%s' in GIMP%s.\n")%(self.img.name, str(version))\
            +_("# Base colour type is '%s' for this image of size = %dx%d px.\n")\
            %(enum_type[self.img.base_type * 2], self.img.width, self.img.height)\
            +_("# The classification 'Group' means has child(s) while 'Single' has not.\n")\
            +_("# Note: in text variable the newline have been replaced by '/'.\n\n")

        cr = 1  # the position of the layer
        for l in self.layers:    # all the layers
            if version >= (2, 8, 0): childs = l.children
            else: childs = None
            if childs: 
                tag = tags[0]
                children = _(" Childs=%s,")%(str([c.name.replace("\n", "/") for c in childs]))
                # here: '.replace("\n", "/")' is there for naming consistency only
            else: 
                tag = tags[1]
                children = ""
            # file the content for each layer and add the parasite info list
            n, paras = get_parasite_list(l)
            if n == 0: dot = ' .'
            else: dot = ' :'
            txt += _("%d%sname=\"%s\", Offsets=(%d , %d), WidthxHeight=%dx%d px,%s Parasite=%d%s\n")\
                %(cr, tag, l.name.replace("\n", "/"), l.width, l.height, l.offsets[0], l.offsets[1],  children, n, dot)
            for p in paras:
                paras_text = str(l.parasite_find(p))
                paras_text = paras_text.strip(chr(0))
                paras_text = paras_text.replace("\n", "/")
                txt.rstrip()                
                txt += "    -> %s = \"%s\"\n"%(p, paras_text)
            cr += 1
        
        # file: user chosen file-name ("%s_layout.txt"%self.img.name)
        chooser = gtk.FileChooserDialog(title=_("User file selection"),
                                    action=gtk.FILE_CHOOSER_ACTION_SAVE,
                                    buttons=(gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
                                             gtk.STOCK_SAVE, gtk.RESPONSE_OK))
        chooser.set_current_name(os.path.basename("%s_layout.txt"%self.img.name))
        la = gtk.Label(_("Suggestion: you can use a folder like '.../Images/layouts/' for this file."))
        la.show()
        chooser.set_extra_widget(la)
        # could be the folder of the open image as default?
        if self.img.filename: chooser.set_current_folder(os.path.dirname(self.img.filename))

        response = chooser.run()
        if response != gtk.RESPONSE_OK:
            chooser.destroy()
            gimp.message(_("INFO: save was aborted by the user"))
            return
        filename = chooser.get_filename()

        if filename:
            try:
                file_obj = open(filename, "w")
                file_obj.write(txt);
                file_obj.close()
                # for a file save ->
                btn.set_label(_("Save all (done)"))
                self.pre_save = self.names
                self.flag_save = True
            except:
                gimp.message(_("ERROR in saving file: ")+filename)
        else: gimp.message(_("ERROR: no file-name given!"))

        chooser.destroy()
        return

### Helper functions ###########################################################

def get_all_layers(parent):
    """
    Layers traversal for GIMP > 2.7, but work also for 2.6 .
    Get all layers recursively from 'parent', either an Image or a GroupLayer.
    Proceeds depth-first. From 'Seldom Needy'
    """
    container=[]
    for layer in parent.layers:
        container.append(layer)
        if hasattr(layer,"layers"):
            container.extend(get_all_layers(layer) )
    return container

def get_parasite_list(item):
    # adaptation to GIMP version?
    if version > (2, 8, 0): n, parasites = pdb.gimp_item_get_parasite_list(item)
    else: n, parasites = pdb.gimp_drawable_parasite_list(item)
    return(n, parasites)

### Main procedure #############################################################

def info_layers (img, drw):
    global stop
    # avoid duplicate launch
    if shelf.has_key('info_layers') and shelf['info_layers']:
        gimp.message(_("WARNING: an 'info_layers' instance is already running!"))
    else:
        shelf['info_layers'] = True

        r = LayerInfo(img, drw)
        gtk.main()

        shelf['info_layers'] = False
        stop = True

register(
        'info_layers',
        _("Display actual infos on the active layer, managed a 'layer-info' parasite and an all info file.\nFrom: ")+fi,
        _("Display a window with live infos on the selected layer; \ncontrols are ")\
            +_("a ComboBox for selection, 'Enter text' for parasite and 'Save all' for file."),
        'David Marquez de la Cruz, R. Brizard',
        '(GPL 2)',
        '2014',
        _("Layer-info..."),
        '*',  # imagetypes
        [
          (PF_IMAGE, "img", "IMAGE:", None),
          (PF_DRAWABLE, "drw", "DRAWABLE:", None)
        ], # Parameters
        [], # Results
        info_layers,
        menu="<Image>"+_("/Extensions/Plugins-Python/Layer"),
        domain=( "info_layers", locale_directory)
        )

main()
