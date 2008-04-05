'''
profiles.py

Copyright 2007 Andres Riancho

This file is part of w3af, w3af.sourceforge.net .

w3af is free software; you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation version 2 of the License.

w3af is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with w3af; if not, write to the Free Software
Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA
'''

import pygtk
pygtk.require('2.0')
import gtk

import core.ui.gtkUi.helpers as helpers
import core.ui.gtkUi.entries as entries
from core.controllers.misc import parseOptions

class ProfileList(gtk.TreeView):
    '''A list showing all the profiles.

    @param w3af: The main core class.
    @param initial: The profile to start

    @author: Facundo Batista <facundobatista =at= taniquetil.com.ar>
    '''
    def __init__(self, w3af, initial=None):
        self.w3af = w3af

        # create the ListStore, with the info listed below
        self.liststore = gtk.ListStore(str, str, str, int, str)

        # we will keep the profile instances here
        self.profile_instances = {None:None}

        # build the list with the profiles name, description, id, changed, permanentname
        self.liststore.append(["Empty profile", "Clean profile with nothing configured", None, 0, "Empty profile"])
        for profile in sorted(w3af.getProfileList()):
            nom = profile.getName()
            desc = profile.getDesc()
            prfid = str(id(profile))
            self.profile_instances[prfid] = profile
            self.liststore.append([nom, desc, prfid, 0, nom])

        # create the TreeView using liststore
        super(ProfileList,self).__init__(self.liststore)

        # select the indicated one
        self.selectedProfile = None
        if initial is None:
            self.set_cursor(0)
        else:
            for i, (nom, desc, prfid, changed, perm) in enumerate(self.liststore):
                if initial == nom:
                    self.set_cursor(i)
                    self._useProfile()
                    break
            else:
                raise SystemExit("The profile %r does not exists!" % initial)
        
        # callbacks for right button and select
        self.connect('button-press-event', self._changeAtempt)
        self.connect('button-release-event', self._popupMenu)
        self.connect('cursor-changed', self._useProfile)
        self._rightButtonMenu = None
        
        # create a TreeViewColumn for the text
        tvcolumn = gtk.TreeViewColumn('Profiles')
        cell = gtk.CellRendererText()
        tvcolumn.pack_start(cell, True)
        tvcolumn.add_attribute(cell, 'markup', 0)
        self.append_column(tvcolumn)

        # put the tooltips if supported
        if hasattr(self, "set_tooltip_column"):
            self.set_tooltip_column(1)

        # here we keep the info exactly like the core, to change it
        # easily to it
        self.pluginsConfigs = {None:{}}
        self.origActPlugins = sorted(self.w3af.mainwin.pcbody.getActivatedPlugins())

        self.show()

    def _controlDifferences(self):
        '''Returns if something is different agains initial state.'''
        # Always check activation status
        nowActive = sorted(self.w3af.mainwin.pcbody.getActivatedPlugins())
        if nowActive != self.origActPlugins:
            return True

        # Check plugins config
        for ptype in self.w3af.getPluginTypes():
            for pname in self.w3af.getPluginList(ptype):
                opts = self.w3af.getPluginOptions(ptype, pname)
                if not opts:
                    continue

                # let's see if we have it (if we don't, it means
                # we never got into that plugin, therefore it's ok
                if (ptype,pname) not in self.pluginsConfigs:
                    continue

                # compare it
                savedconfig = self.pluginsConfigs[(ptype,pname)]
                for (k, origv) in savedconfig.items():
                    newv = str(opts[k])
                    if newv != origv:
                        return True

        return False

    def pluginChanged(self, plugin=None):
        '''Get executed when a plugin is changed.

        @param plugin: The plugin which changed.

        When executed, this check if the saved config is equal or not to the 
        original one, and enables color and buttons.
        '''
        changed = self._controlDifferences()

        # update boldness and info
        path = self.get_cursor()[0]
        row = self.liststore[path]
        row[3] = changed
        if changed:
            row[0] = "<b>%s</b>" % row[4]
        else:
            row[0] = row[4]

        # update the mainwin buttons
        newstatus = self._getActionsSensitivity(path)
        self.w3af.mainwin.activateProfileActions(newstatus)

    def pluginConfig(self, plugin):
        '''Gets executed when a plugin config panel is created.

        @param plugin: The plugin which will be configured.

        When executed, takes a snapshot of the original plugin configuration.
        '''
        # only stores the original one
        if (plugin.ptype,plugin.pname) in self.pluginsConfigs:
            return

        # we adapt this information to a only-options dict, as that's
        # the information that we can get later from the core
        xmlopts = plugin.getOptionsXML()
        if xmlopts is not None:
            opts = parseOptions.parseXML(xmlopts)
        else:
            opts = None
        realopts = {}
        for nom,config in opts.items():
            realopts[nom] = config["default"]
        self.pluginsConfigs[(plugin.ptype,plugin.pname)] = realopts

    def _changeAtempt(self, widget, event):
        '''Let the user change profile if the actual is saved.'''
        path = self.get_cursor()[0]
        row = self.liststore[path]
        if row[3]:
            # The profile is changed
            if event.button != 1:
                return True

            # Clicked with left button
            msg = "Do you want to discard the changes in the Profile?"
            dlg = gtk.MessageDialog(None, gtk.DIALOG_MODAL, gtk.MESSAGE_WARNING, gtk.BUTTONS_YES_NO, msg)
            stayhere = dlg.run() != gtk.RESPONSE_YES
            dlg.destroy()
            if not stayhere:
                # even if it's modified, we're leaving it: when we come back, the previous
                # configuration will be loaded... so here we just unbold it and set it as 
                # not modified 
                row[0] = row[4]
                row[3] = False
                self.w3af.mainwin.sb("The previous profile configuration was discarded")
            return stayhere
        return False

    def _popupMenu( self, tv, event ):
        '''Shows a menu when you right click on a plugin.
        
        @param tv: the treeview.
        @parameter event: The GTK event 
        '''
        if event.button != 3:
            return

        # don't allow right button in other widget if actual is not saved
        path = self.get_cursor()[0]
        row = self.liststore[path]
        posic = self.get_path_at_pos(int(event.x), int(event.y))
        if posic is None:
            return
        clickpath = posic[0]
        if row[3] and clickpath != path:
            return True

        # creates the whole menu only once
        if self._rightButtonMenu is None:
            gm = gtk.Menu()
            self._rightButtonMenu = gm
        
            # the items
            e = gtk.MenuItem("Save configuration to profile")
            e.connect('activate', self.saveProfile)
            gm.append(e)
            e = gtk.MenuItem("Save configuration to a new profile")
            e.connect('activate', self.saveAsProfile)
            gm.append(e)
            e = gtk.MenuItem("Revert to saved profile state")
            e.connect('activate', self.revertProfile)
            gm.append(e)
            e = gtk.MenuItem("Delete this profile")
            e.connect('activate', self.deleteProfile)
            gm.append(e)
            gm.show_all()
        else:
            gm = self._rightButtonMenu
        
        (path, column) = tv.get_cursor()
        # Is it over a plugin name ?
        if path != None and len(path) == 1:
            # Enable/disable the options in function of state
            newstatus = self._getActionsSensitivity(path)
            children = gm.get_children()
            for child,stt in zip(children, newstatus):
                child.set_sensitive(stt)
                
            gm.popup( None, None, None, event.button, event.time)

    def _getActionsSensitivity(self, path):
        '''Returns which actions must be activated or not

        @param path: where the cursor is located
        @return: four booleans indicating the state for each option
        '''
        vals = []
        row = self.liststore[path]

        # save: enabled if it's modified and it's not the Default
        vals.append(row[3] and path[0] != 0)
        # save as: always enabled
        vals.append(True)
        # revert: enabled if it's modified
        vals.append(row[3])
        # delete: enabled if it's not the Default
        vals.append(path[0] != 0)

        return vals

    def _getProfileName(self):
        '''Gets the actual profile instance.

        @return: The profile instance for the actual cursor position.
        '''
        (path, focus) = self.get_cursor()
        prfid = self.liststore[path][2]
        profile = self.profile_instances[prfid]
        if profile is None:
            return None
        return profile.getName()

    def _useProfile(self, widget=None):
        '''Uses the selected profile.'''
        profile = self._getProfileName()
        if profile == self.selectedProfile:
            return
        self.selectedProfile = profile

        self.w3af.useProfile(profile)
        self.w3af.mainwin.pcbody.reload()
        self.w3af.mainwin.sb("Profile changed")

        # get the activated plugins
        self.origActPlugins = self.w3af.mainwin.pcbody.getActivatedPlugins()

        # update the mainwin buttons
        path = self.get_cursor()[0]
        newstatus = self._getActionsSensitivity(path)
        self.w3af.mainwin.activateProfileActions(newstatus)

    def saveProfile(self, widget=None):
        '''Saves the selected profile.'''
        profileName = self._getProfileName()
        #FIXME: There is a problem here! When I click on a plugin to enable it (on the gtk ui)
        # the ui doesn't tell that to the core, so when I call saveCurrentToProfile; the core doesn't
        # have that plugin enabled and it won't save that to the profile!!
        self.w3af.saveCurrentToProfile( profileName )
        #FIXME: Saving the profile should put the name of the profile back to non-bold and
        # let me navigate away from the profile.
        
        self.w3af.mainwin.sb("Profile saved")

    def saveAsProfile(self, widget=None):
        '''Copies the selected profile.'''
        profile = self._getProfileName()
        # FIXME: Please also ask for a profile description and use it !
        profileDescription = ''
        dlg = entries.EntryDialog("Save as...")
        dlg.run()
        filename = dlg.inputtext
        dlg.destroy()
        if filename is not None:
            self.w3af.saveCurrentToNewProfile( filename , profileDescription )
            # FIXME: Here you should reload the profile list
            self.w3af.mainwin.sb("New profile created")

    def revertProfile(self, widget=None):
        '''Reverts the selected profile to its saved state.'''
        msg = "Do you really want to discard the changes in the the profile and load the previous saved configuration?"
        dlg = gtk.MessageDialog(None, gtk.DIALOG_MODAL, gtk.MESSAGE_WARNING, gtk.BUTTONS_YES_NO, msg)
        opt = dlg.run()
        dlg.destroy()

        if opt == gtk.RESPONSE_YES:
            self.selectedProfile = -1
            path = self.get_cursor()[0]
            row = self.liststore[path]
            row[0] = row[4]
            row[3] = False
            self._useProfile()
            self.w3af.mainwin.sb("The profile configuration was reverted to its last saved state")

    def deleteProfile(self, widget=None):
        '''Deletes the selected profile.'''
        profile = self._getProfileName()

        msg = "Do you really want to DELETE the profile '%s'?" % profile
        dlg = gtk.MessageDialog(None, gtk.DIALOG_MODAL, gtk.MESSAGE_WARNING, gtk.BUTTONS_YES_NO, msg)
        opt = dlg.run()
        dlg.destroy()

        if opt == gtk.RESPONSE_YES:
            self.w3af.removeProfile( profile )
            # FIXME: Here you should reload the profile list
            self.w3af.mainwin.sb("The profile was deleted")
