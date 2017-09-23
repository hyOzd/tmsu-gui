#!/usr/bin/python3
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk

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
            r = self._cmd('tags -n {}'.format(fileName))
            return r.split(':')[1].split()
        return self._cmd('tags').splitlines()

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

class MyWindow(Gtk.Window):
    def __init__(self):
        Gtk.Window.__init__(self, title="Tags")
        self.set_size_request(300, 400)

        self.vbox = Gtk.Box(parent = self,
                            orientation = Gtk.Orientation.VERTICAL)

        self.store = Gtk.ListStore(str, bool) # tag
        self.list_widget = Gtk.TreeView(self.store)
        col = Gtk.TreeViewColumn("Tags", Gtk.CellRendererText(), text=0)
        col.set_expand(True)
        self.list_widget.append_column(col)
        col = Gtk.TreeViewColumn("Checked", Gtk.CellRendererToggle(), active=1)
        self.list_widget.append_column(col)
        self.vbox.pack_start(self.list_widget, True, True, 0)

        hbox = Gtk.Box(orientation = Gtk.Orientation.HORIZONTAL)
        self.tag_edit = Gtk.Entry()
        self.add_button = Gtk.Button(label = "Add")
        hbox.pack_start(self.tag_edit, True, True, 0)
        hbox.pack_end(self.add_button, False, False, 0)
        self.vbox.pack_end(hbox, False, False, 0)

        # test data
        self.store.append(["tag", True])
        self.store.append(["tagm", True])
        self.store.append(["dfdf", True])
        self.store.append(["kkasd", False])

if __name__ == "__main__":
    err = None
    tmsu = Tmsu.findTmsu()
    if not tmsu:
        err = "tmsu executable not found!"
    elif tmsu.info() == None:
        err = "No tmsu database is found."

    if err:
        dialog = Gtk.MessageDialog(
            None, 0, Gtk.MessageType.INFO,
            Gtk.ButtonsType.OK, err)
        dialog.run()
    else:
        print(tmsu.info())
        print(tmsu.tags("testfile"))
        win = MyWindow()
        win.connect('delete-event', Gtk.main_quit)
        win.show_all()
        Gtk.main()
