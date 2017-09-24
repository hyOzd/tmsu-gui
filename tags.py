#!/usr/bin/python3
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk

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
        """Returns a list of tags. If fileName is provided, list item is a tuple of
        (tagname, value) pair."""
        if fileName:
            # Note: tmsu behaves differently for 'tags' command when used
            # interactively and called from scripts. That's why we add '-n'.
            r = self._cmd('tags -n "{}"'.format(fileName))
            tag_value = []
            for tag in r.split(':')[1].split():
                tv = tag.split("=")
                if len(tv) > 1:
                    tag_value.append((tv[0], tv[1]))
                else:
                    tag_value.append((tv[0], ""))
            return tag_value
        else:
            return self._cmd('tags').splitlines()

    def tag(self, fileName, tagName, value=None):
        try:
            self._cmd('tag "{}" {}{}'.format(fileName, tagName,
                                             "="+value if value else ""))
            return True
        except sp.CalledProcessError as e:
            print("Failed to tag file.")
            return False

    def untag(self, fileName, tagName, value=None):
        try:
            self._cmd('untag "{}" {}{}'.format(fileName, tagName,
                                               "="+value if value else ""))
            return True
        except sp.CalledProcessError as e:
            print("Failed to untag file.")
            return False

    def rename(self, tagName, newName):
        try:
            self._cmd('rename {} {}'.format(tagName, newName))
            return True
        except sp.CalledProcessError as e:
            print("Failed to rename tag.")
            return False

    def values(self, tagName=None):
        try:
            r = self._cmd('values {}'.format(tagName if tagName else ""))
            return r.split()
        except sp.CalledProcessError as e:
            print("Failed to get value list.")
            return False

    def delete(self, tagName):
        try:
            self._cmd('delete {}'.format(tagName))
            return True
        except sp.CalledProcessError as e:
            print("Failed to delete tag: {}".format(tagName))
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
    NAME = 1
    VALUE = 2

class MyWindow(Gtk.Window):
    def __init__(self, tmsu, fileName):
        Gtk.Window.__init__(self, title="Tags")

        self.tmsu = tmsu
        self.fileName = fileName

        self.set_size_request(300, 400)
        self.vbox = Gtk.Box(parent = self,
                            orientation = Gtk.Orientation.VERTICAL)
        self.store = Gtk.ListStore(bool, str, str)
        self.list_widget = Gtk.TreeView(self.store)
        self.vbox.pack_start(self.list_widget, True, True, 0)

        # 'tagged' checkbox column
        cell = Gtk.CellRendererToggle()
        cell.connect("toggled", self.on_cell_toggled)
        col = Gtk.TreeViewColumn("", cell, active=TagCol.TAGGED)
        col.set_sort_column_id(TagCol.TAGGED)
        self.list_widget.append_column(col)
        self.list_widget.connect('key-press-event', self.on_key_press)

        # tag name column
        cell = Gtk.CellRendererText(editable=True)
        cell.connect("edited", self.on_tagName_edited)
        col = Gtk.TreeViewColumn("Tag", cell, text=TagCol.NAME)
        col.set_expand(True)
        col.set_sort_column_id(TagCol.NAME)
        self.list_widget.append_column(col)

        # tag value column
        cell = Gtk.CellRendererText(editable=True)
        cell.connect("edited", self.on_tagValue_edited)
        cell.connect("editing-started", self.on_tagValue_editing_started)
        col = Gtk.TreeViewColumn("Value", cell, text=TagCol.VALUE)
        col.set_expand(True)
        col.set_sort_column_id(TagCol.VALUE)
        self.list_widget.append_column(col)

        hbox = Gtk.Box(orientation = Gtk.Orientation.HORIZONTAL)

        # tag name edit
        self.tag_edit = Gtk.Entry()
        self.tag_edit.set_placeholder_text("Tag")
        self.tag_edit.connect('activate', self.on_add_clicked)
        completion = Gtk.EntryCompletion(model=self.store)
        completion.set_text_column(TagCol.NAME)
        completion.set_inline_completion(True)
        self.tag_edit.set_completion(completion)

        # tag value edit
        self.value_edit = Gtk.Entry()
        self.value_edit.set_placeholder_text("Value")
        self.value_edit.connect('activate', self.on_add_clicked)
        completion = Gtk.EntryCompletion(model=self.store)
        completion.set_text_column(TagCol.VALUE)
        completion.set_inline_completion(True)
        completion.set_match_func(self.value_edit_compl_match)
        self.value_edit.set_completion(completion)

        # tag add button
        self.add_button = Gtk.Button(label = "Add")
        self.add_button.connect('clicked', self.on_add_clicked)
        hbox.pack_start(self.tag_edit, True, True, 0)
        hbox.pack_start(self.value_edit, True, True, 0)
        hbox.pack_end(self.add_button, False, False, 0)
        self.vbox.pack_end(hbox, False, False, 0)

        self.loadTags()

    def on_cell_toggled(self, widget, path):
        self.toggleTag(path)

    def toggleTag(self, path):
        tagName = self.store[path][TagCol.NAME]
        isTagged = self.store[path][TagCol.TAGGED]
        if not isTagged:
            r = self.tagFile(tagName)
        else:
            tagValue = self.store[path][TagCol.VALUE]
            r = self.untagFile(tagName, tagValue)

        # toggle
        if r:
            self.store[path][TagCol.TAGGED] = not self.store[path][TagCol.TAGGED]
            if isTagged: self.store[path][TagCol.VALUE] = ""

    def on_tagName_edited(self, widget, path, newName):
        tagName = self.store[path][TagCol.NAME]
        if newName == tagName: return
        if self.renameTag(tagName, newName):
            self.store[path][TagCol.NAME] = newName

    def on_tagValue_edited(self, widget, path, value):
        tagName = self.store[path][TagCol.NAME]
        isTagged = self.store[path][TagCol.TAGGED]
        oldValue = self.store[path][TagCol.VALUE]
        if value == oldValue: return
        if isTagged:        # untag to prevent duplicate
            if not self.untagFile(tagName, oldValue):
                return
        if self.tagFile(tagName, value):
            self.store[path][TagCol.VALUE] = value
            self.store[path][TagCol.TAGGED] = True

    def on_tagValue_editing_started(self, widget, editable, path):
        tagName = self.store[path][TagCol.NAME]
        options = self.tmsu.values(tagName)
        if options:
            store = Gtk.ListStore(str)
            for val in options:
                store.append([val])
            completion = Gtk.EntryCompletion(model=store)
            completion.set_text_column(0)
            completion.set_inline_completion(True)
            editable.set_completion(completion)

    def value_edit_compl_match(self, compl, key, it):
        rowTag = self.store.get_value(it, TagCol.NAME)
        editTag = self.tag_edit.get_text()
        if editTag and rowTag == editTag:
            return True
        else:
            return False

    def on_add_clicked(self, widget):
        tagName = self.tag_edit.get_text().strip()
        tagValue = self.value_edit.get_text().strip()
        if len(tagName) == 0:
            self.displayError("Enter a tag name!")
            return

        tagRow = self.findTag(tagName)
        if tagRow and tagRow[TagCol.VALUE] and not tagValue:
            self.displayError("You need to enter a value for this tag!")
            return

        if self.tagFile(tagName, tagValue):
            self.tag_edit.set_text("")
            self.value_edit.set_text("")
            if tagRow:              # tag already exists
                tagRow[TagCol.TAGGED] = True
                tagRow[TagCol.VALUE] = tagValue
            else:                   # new tag
                self.store.append([True, tagName, tagValue])

    def on_key_press(self, widget, ev):
        key = Gdk.keyval_name(ev.keyval)
        if key == 'Delete':
            self.on_delete_key()
            return True
        elif key == 'space':
            self.on_space_key()
            return True
        return False

    def on_delete_key(self):
        sel = self.list_widget.get_selection()
        mod, it = sel.get_selected()
        tagName = mod.get_value(it, TagCol.NAME)

        # ask confirmation
        msg = 'Are you sure to delete tag "{}"?'.format(tagName)
        dialog = Gtk.MessageDialog(
            self, Gtk.DialogFlags.MODAL, Gtk.MessageType.WARNING,
            Gtk.ButtonsType.OK_CANCEL, msg)
        r = dialog.run()
        dialog.destroy()

        if r == Gtk.ResponseType.OK and self.deleteTag(tagName):
            mod.remove(it)

    def on_space_key(self):
        sel = self.list_widget.get_selection()
        mod, it = sel.get_selected()
        self.toggleTag(mod.get_path(it))

    def findTag(self, tagName):
        """Find a tag in current listing."""
        for row in self.store:
            if row[TagCol.NAME] == tagName:
                return row
        return None

    def tagFile(self, tagName, tagValue=None):
        """Tags a file and shows error message if fails."""
        if not self.tmsu.tag(self.fileName, tagName, tagValue):
            self.displayError("Failed to tag file.")
            return False
        return True

    def untagFile(self, tagName, tagValue=None):
        """Untags a file and shows error message if fails."""
        if not self.tmsu.untag(self.fileName, tagName, tagValue):
            self.displayError("Failed to untag file.")
            return False
        return True

    def renameTag(self, tagName, newName):
        """Renames a tag and shows error message if fails."""
        # TODO: if tagname already exists show merge warning
        if not self.tmsu.rename(tagName, newName):
            self.displayError("Failed to rename tag.")
            return False
        return True

    def loadTags(self):
        """Loads tags for the first time."""
        allTags = self.tmsu.tags()
        fileTags = self.tmsu.tags(self.fileName)
        fileTagNames=[]
        for tag in fileTags:
            self.store.append([True, tag[0], tag[1]])
            fileTagNames.append(tag[0])
        for tag in allTags:
            if not tag in fileTagNames:
                self.store.append([False, tag, ""])

    def deleteTag(self, tagName):
        """Deletes a tag and shows error if fails."""
        if not self.tmsu.delete(tagName):
            self.displayError("Failed to delete tag: {}".format(tagName))
            return False
        return True

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
