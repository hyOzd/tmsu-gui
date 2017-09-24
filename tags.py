#!/usr/bin/python3
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk

import sys, os, enum
import subprocess as sp

class Tmsu:
    def __init__(self, tmsu):
        self.tmsu = tmsu

    def info(self):
        try:
            r = self._cmd('info')
        except sp.CalledProcessError as e:
            if e.returncode == 1: # database doesn't exist
                return None
        lines = r.splitlines()
        def psplit(l): return map(lambda x: x.strip(), l.split(':'))
        d = dict(map(psplit, lines))

        return {'root': d['Root path'],
                'size': d['Size'],
                'database':d['Database']}

    def tags(self, fileName=None):
        if fileName:
            # Note: tmsu behaves differently for 'tags' command when used
            # interactively and called from scripts.
            r = self._cmd('tags -n "{}"'.format(fileName))
            return r.split(':')[1].split()
        return self._cmd('tags').splitlines()

    def tag(self, fileName, tagName):
        try:
            self._cmd('tag "{}" {}'.format(fileName, tagName))
            return True
        except sp.CalledProcessError as e:
            print("Failed to tag file.")
            return False

    def untag(self, fileName, tagName):
        try:
            self._cmd('untag "{}" {}'.format(fileName, tagName))
            return True
        except sp.CalledProcessError as e:
            print("Failed to untag file.")
            return False

    def _cmd(self, cmd):
        return sp.check_output('tmsu ' + cmd, shell=True).decode('utf-8')

    @staticmethod
    def findTmsu():
        import shutil
        tmsu =  shutil.which("tmsu")
        if tmsu:
            return Tmsu(tmsu)
        else:
            return None

@enum.unique
class TagCol(enum.IntEnum):
    TAGGED = 0
    TAGNAME = 1

class MyWindow(Gtk.Window):
    def __init__(self, tmsu, fileName):
        Gtk.Window.__init__(self, title="Tags")

        self.tmsu = tmsu
        self.fileName = fileName

        self.set_size_request(300, 400)
        self.vbox = Gtk.Box(parent = self,
                            orientation = Gtk.Orientation.VERTICAL)
        self.store = Gtk.ListStore(bool, str)
        self.list_widget = Gtk.TreeView(self.store)
        self.vbox.pack_start(self.list_widget, True, True, 0)

        # 'tagged' checkbox column
        cell = Gtk.CellRendererToggle()
        cell.connect("toggled", self.on_cell_toggled)
        col = Gtk.TreeViewColumn("", cell, active=TagCol.TAGGED)
        col.set_sort_column_id(TagCol.TAGGED)
        self.list_widget.append_column(col)

        # tag name column
        col = Gtk.TreeViewColumn("Tag", Gtk.CellRendererText(editable=True),
                                 text=TagCol.TAGNAME)
        col.set_expand(True)
        col.set_sort_column_id(TagCol.TAGNAME)
        self.list_widget.append_column(col)

        hbox = Gtk.Box(orientation = Gtk.Orientation.HORIZONTAL)
        self.tag_edit = Gtk.Entry()
        self.tag_edit.connect('activate', self.on_add_clicked)
        completion = Gtk.EntryCompletion(model=self.store)
        completion.set_text_column(TagCol.TAGNAME)
        completion.set_inline_completion(True)
        self.tag_edit.set_completion(completion)

        self.add_button = Gtk.Button(label = "Add")
        self.add_button.connect('clicked', self.on_add_clicked)
        hbox.pack_start(self.tag_edit, True, True, 0)
        hbox.pack_end(self.add_button, False, False, 0)
        self.vbox.pack_end(hbox, False, False, 0)

        self.loadTags()

    def on_cell_toggled(self, widget, path):
        tagName = self.store[path][TagCol.TAGNAME]
        isTagged = self.store[path][TagCol.TAGGED]
        if not isTagged:
            r = self.tagFile(tagName)
        else:
            r = self.untagFile(tagName)

        # toggle
        if r: self.store[path][TagCol.TAGGED] = not self.store[path][TagCol.TAGGED]

    def on_add_clicked(self, widget):
        tagName = self.tag_edit.get_text().strip()
        if len(tagName) == 0:
            self.displayError("Enter a tag name!")
            return

        tagRow = self.findTag(tagName)

        if tagRow and tagRow[TagCol.TAGGED]: # already tagged
            self.tag_edit.set_text("")
            return

        if self.tagFile(tagName):
            self.tag_edit.set_text("")
            if tagRow:              # tag already exists
                tagRow[TagCol.TAGGED] = True
            else:                   # new tag
                self.store.append([True, tagName])

    def findTag(self, tagName):
        """Find a tag in current listing."""
        for row in self.store:
            if row[TagCol.TAGNAME] == tagName:
                return row
        return None

    def tagFile(self, tagName):
        """Tags a file and shows error message if fails."""
        if not self.tmsu.tag(self.fileName, tagName):
            self.displayError("Failed to tag file.")
            return False
        return True

    def untagFile(self, tagName):
        """Untags a file and shows error message if fails."""
        if not self.tmsu.untag(self.fileName, tagName):
            self.displayError("Failed to untag file.")
            return False
        return True

    def loadTags(self):
        """Loads tags for the first time."""
        allTags = self.tmsu.tags()
        fileTags = self.tmsu.tags(self.fileName)
        for tag in fileTags:
            self.store.append([True, tag])
        for tag in allTags:
            if not tag in fileTags:
                self.store.append([False, tag])

    def displayError(self, msg):
        """Display given error message in a message box."""
        dialog = Gtk.MessageDialog(
            self, Gtk.DialogFlags.MODAL, Gtk.MessageType.ERROR,
            Gtk.ButtonsType.CLOSE, msg)
        dialog.run()
        dialog.destroy()

if __name__ == "__main__":
    err = None
    tmsu = Tmsu.findTmsu()
    if not tmsu:
        err = "tmsu executable not found!"
    elif len(sys.argv) !=2:
        err = "Invalid arguments."
    else:
        fileName = sys.argv[1]
        os.chdir(os.path.dirname(fileName))
        if tmsu.info() == None:
            err = "No tmsu database is found."


    if err:
        dialog = Gtk.MessageDialog(
            None, 0, Gtk.MessageType.INFO,
            Gtk.ButtonsType.OK, err)
        dialog.run()
    else:

        win = MyWindow(tmsu, sys.argv[1])
        win.connect('delete-event', Gtk.main_quit)
        win.show_all()
        Gtk.main()
