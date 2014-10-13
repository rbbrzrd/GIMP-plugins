#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
# Inspired by David Maquez de la Cruz (at http://registry.gimp.org/node/26317) (c) 2012
   seems based on 'ratio_info.py' from Joao S. Bueno in 2007.
 June 2014, by Robert Brizard:
    1) adding text explanations (date, etc...), about the layer, in a layer parasite;
    2) plug-in auto quit if no layer or initial image;
    3) permitting internationalization in 'user' folders;
    4) only one launch at a time;
    5) save the info for all layers in a text file.
 August 2014 version 0.1:
    1) an alternate way to select the active layer;
    2) display two others properties: position and type;
    3) harmonizing between info in display and in text file.
 October 2014 version 0.2 (goal more staying power):
    1) exchange editing in 'layer dialog' and live info for simplifying reading layer 
        like a 'PDF' convert to a 'XCF' and more layers in one session. 

   Make sense, fully, for 'XCF' file.
================================================================================
 You may use and distribute this plug-in under the terms of the GPL 2 or greater.
 Get the license text at "http://www.gnu.org/licenses/" 
"""

import gtk, pango
import os, sys, gettext

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

enum_type = [_('RGB'), _('RGBA'), _('GRAY'), _('GRAYA'), _('INDEXED'), _('INDEXEDA')]
prob = _("ERROR: the layer object list isn't the same!\n  Plug-in has auto quitted.")
# store the initial layer visibility state to restore it
layer_view = []
layers = []

version = gimp.version
start_minver = 6 # minor version of the previous GIMP-2.6

### GUI integration ############################################################

class LayerViewer(gtk.Window):
    def __init__ (self, img, drw, *args):
        global layer_view, layers
        self.img = img
        self.drw = drw

        self.txt = _("    Type : %s  \n    Name : %s  \n    Offsets(x,y) : (%d , %d) px")\
            +_("    \n    Size(W*H) : %d*%d px  \n    Parasite : %d , %s")

        self.flag_paras = False # track 'Enter text' after a 'Save all'
        self.flag_save = False  # track 'Save all (done)'

        # construct the plug-in window
        r =  gtk.Window.__init__(self, *args)
        # The window manager quit signal:
        self.connect("destroy", gtk.main_quit)  

        self.set_title(_("INFO on exclusive view layer"))

        vbox = gtk.VBox(spacing=6, homogeneous=False)
        hbox = gtk.HBox(homogeneous=False, spacing=6)

        # special line for number of layer choice
        self.combo_box = gtk.combo_box_new_text() #gtk.ComboBox()
        #self.combo_box.set_wrap_width(1)
        self.combo_box.set_has_tooltip(True)
        self.combo_box.set_tooltip_text(_("Its the selected number of the exclusive view layer.")\
            +_("\nIf you see this message, you can scroll with the mouse wheel or ")\
            +_("click to select.\n     WARNING : don't edit in the 'Layer Dialog' and")\
            +_(" the window is current at the time of that selection only."))
        self.combo_box.connect("changed", self.name_change)
        #self.combo_box.style.arrow_size = 20   # no error but don't works
        hbox.add(self.combo_box)

        # icon to indicate where it applies
        stock_ic = gtk.Image()
        stock_ic.set_from_stock(gtk.STOCK_GO_BACK, gtk.ICON_SIZE_BUTTON)
        hbox.add(stock_ic)
        label_sel =  gtk.Label(_("Exclusive view layer "))
        hbox.add(label_sel)
        vbox.add(hbox)

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

        table = gtk.Table(rows=1, columns=2, homogeneous=False)
        table.set_col_spacings(3)
        vbox.add(table)
        # label for the managed parasite 
        self.label1 = gtk.Label()
        self.label1.set_label("<span foreground='blue' background='white' >"\
            +' layer-info: '+"</span>")
        self.label1.set_use_markup(True)
        self.label1.set_has_tooltip(True)
        self.label1.set_tooltip_text(_("Name of the layer parasite manage by this plug-in."))
        table.attach(self.label1, 0, 1, 0, 1, xoptions=gtk.FILL, yoptions=0)

        # text in or should be in the managed parasite
        self.entry = gtk.Entry(max=0)
        self.entry.set_has_tooltip(True)
        self.entry.set_tooltip_text(_("Display text for layer parasite: 'layer-info'")\
            +_(".\nIt permits editing or creating that parasite."))
        table.attach(self.entry, 1, 2, 0, 1)

        # add action buttons
        hbox = gtk.HBox(homogeneous=False, spacing=6)
        btn = gtk.Button(_("Enter text"),  gtk.STOCK_EDIT)
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

        # populate the combo_box
        layers = get_all_layers(self.img)
        #self.names = [lay.name.replace("\n", "/").replace("'", "\'") for lay in self.layers]
        max_pos = len(layers)
        for i in range(max_pos): 
            self.combo_box.append_text(_("Layer #%d")%(i+1))
            layer_view.append(layers[i].visible)

        # completes this window, name
        self.add(vbox)
        self.show_all()
        self.set_keep_above(True)

        #this call self.name_change()   #if self.flag_names == True : 
        self.combo_box.set_active(0)
        return r

    def name_change(self, btn, data=None) :
        """
        New layer selection. Take into account a possible edit in the 'Layer Dialog'
        """
        # still the same image?
        img_list = gimp.image_list()
        if (self.img not in img_list) or (len(self.img.layers) == 0) :
            gimp.message(prob)
            gtk.main_quit()
            return
        # check if layers list is the same
        temp_layers = get_all_layers(self.img)
        same_layers = layers == temp_layers
        if same_layers :
            index = btn.get_active()
            # check for possible name change -catch first by 'index == -1'
            if index == -1:
                gimp.message(_("ERROR: the layer name is no longer there!"))
                gtk.main_quit()
                return

            self.layer = layers[index]
            #> layer offsets
            x, y = self.layer.offsets
            #> layer name
            name = temp_layers[index].name.replace("\n", "/").replace("'", "\'")
            #> layer size, name
            h = self.layer.height
            w = self.layer.width
            #> layer type
            _type = self.layer.type
            # Group or Single + ?
            if hasattr(self.layer,"layers"): Type = _("Group, ")+enum_type[_type]
            else: 
                if pdb.gimp_drawable_is_text_layer(self.layer):
                    Type = _("Single text, ")+enum_type[_type]
                else: Type = _("Single, ")+enum_type[_type]
            #> layer parasite
            n, parasites = get_parasite_list(self.layer)

            nflag = parasites.count('layer-info')
            if  nflag == 0:
                paras_text = ''
                flag = _('no')
            else:
                paras_text = str(self.layer.parasite_find('layer-info'))
                # parasite add a zero byte at the end which don't agree with 'gtk.label'
                paras_text = paras_text.strip(chr(0))
                flag = _("yes") # put parasite text in the entry field
            
            # make visibility effect exclusive (also for GroupLayer)
            for L in layers: L.visible = False
            make_layer_visible(self.layer)
            pdb.gimp_displays_flush()

            layer_val = [Type, name, x, y, w , h, n, flag]
            # packing the layer info into text
            txt = self.txt%tuple(layer_val)
            self.label.set_label(txt)

            # and the parasite content
            if  nflag != 0: 
                self.entry.set_text(paras_text)
            else: 
                self.entry.set_text('')

            # reset label on 'Save' button after a save if there some change
            if self.flag_save and self.flag_paras:
                self.btn.set_label(_("Save all"))
                self.flag_save = False

        else :
            gimp.message(prob)
            if len(temp_layers) > 0: 
                make_layer_visible(temp_layers[0])
            gtk.main_quit()

        return

    def add_info(self, btn) :
        """
        Text into the layer parasite 'layer-info'
        """
        paras_text = self.entry.get_text()
        self.layer.attach_new_parasite('layer-info', 1, paras_text)
        self.flag_paras = True
        return
        
    def save_file(self, btn, data=None) :
        """ 
        Create a text file with the info for all layers and their parasites
        """
        
        # for a XML file see  'Python-Fu #3 - Working with Layers and XML in Python-Fu'
        filename = ""
        tags = (_(') Group'), _(') Single'))

        btn.set_label(_("Save all"))    # to reflect prob. if saving more than once
        # start building our text file first by an introduction
        txt = _("# An info layers file for '%s' in GIMP%s.\n")%(self.img.name, str(version))\
            +_("# Base colour type is '%s' for this image of size = %dx%d px.\n")\
            %(enum_type[self.img.base_type * 2], self.img.width, self.img.height)\
            +_("# The classification 'Group' means has child(s) while 'Single' has not.\n")\
            +_("# Note: in text variable the newline have been replaced by '/'.\n\n")

        cr = 1  # the position of the layer
        for L in layers:    # all the layers
            if version >= (2, 8, 0): childs = L.children
            else: childs = None
            if childs: 
                tag = tags[0]
                children = _(" Childs=%s,")%(str([c.name.replace("\n", "/") for c in childs]))
                # here: '.replace("\n", "/")' is there for naming consistency only
            else: 
                tag = tags[1]
                children = ""
            # file the content for each layer and add the parasite info list
            n, paras = get_parasite_list(L)
            if n == 0: dot = ' .'
            else: dot = ' :'
            txt += _("%d%s name=\"%s\", Offsets=(%d , %d), Width*Height=%d*%d px,%s Parasite=%d%s\n")\
                %(cr, tag, L.name.replace("\n", "/"), L.offsets[0], L.offsets[1],\
                 L.width, L.height, children, n, dot)
            for p in paras:
                paras_text = str(L.parasite_find(p))
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
                #self.pre_save = self.names
                self.flag_save = True
                self.flag_paras = False # reset for 'Enter text'
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

def make_layer_visible(layer):
    """ 
    Work for group layer also
    """
    layer.visible = True
    # children visible
    if hasattr(layer,"layers"):
        layers = get_all_layers(layer)
        for L in layers: L.visible = True
    # parent visible
    while layer.parent != None: 
        layer = layer.parent
        layer.visible = True
    return

def get_parasite_list(item):
    # adaptation to GIMP version?
    if version > (2, 8, 0): n, parasites = pdb.gimp_item_get_parasite_list(item)
    else: n, parasites = pdb.gimp_drawable_parasite_list(item)
    return(n, parasites)

### Main procedure #############################################################

def info_layers(img, drw):
    img.undo_group_start()
    # avoid duplicate launch
    if shelf.has_key('info_layers') and shelf['info_layers']:
        gimp.message(_("WARNING: an 'info_layers' instance is already running!"))
    else:
        shelf['info_layers'] = True

        r = LayerViewer(img, drw)
        gtk.main()

        shelf['info_layers'] = False
        if (img in gimp.image_list()):
            layers_aft = get_all_layers(img) 
            if layers_aft == layers: 
                for i in range(len(layers)): layers[i].visible = layer_view[i]
            img.undo_group_end()

register(
        'info_layers',
        _("Display info and manage the selected layer; with an exclusive view, an ")\
            +_("info parasite and also an all info file.\nFrom: ")+fi,
        _("Display a window with info on the selected layer; the controls are ")\
            +_("a ComboBox for layer number selection, 'Enter text' in a layer ")\
            +_("parasite and 'Save all' in a text file."),
        'R. Brizard',
        '((c) GPL 2, R. Brizard)',
        '2014',
        _("Info-layers..."),
        '*',  # any imagetypes
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

