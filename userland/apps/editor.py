#!/usr/bin/env python3
"""
AI-OS Text Editor
Simple text editor application.
"""

import sys
import os

try:
    import gi
    gi.require_version('Gtk', '4.0')
    gi.require_version('GtkSource', '5')
    from gi.repository import Gtk, Gio
    HAS_GTK = True
except ImportError:
    HAS_GTK = False


if HAS_GTK:
    class TextEditor(Gtk.Application):
        def __init__(self):
            super().__init__(application_id='com.aios.editor')
            self.current_file = None
        
        def do_activate(self):
            window = Gtk.ApplicationWindow(application=self, title="Text Editor")
            window.set_default_size(800, 600)
            
            main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
            
            # Header bar
            header = Gtk.HeaderBar()
            header.set_show_title_buttons(True)
            
            # New button
            new_btn = Gtk.Button(label="New")
            new_btn.connect('clicked', self.on_new)
            header.pack_start(new_btn)
            
            # Open button
            open_btn = Gtk.Button(label="Open")
            open_btn.connect('clicked', self.on_open)
            header.pack_start(open_btn)
            
            # Save button
            save_btn = Gtk.Button(label="Save")
            save_btn.connect('clicked', self.on_save)
            header.pack_end(save_btn)
            
            window.set_titlebar(header)
            
            # Text view
            scroll = Gtk.ScrolledWindow()
            scroll.set_vexpand(True)
            
            self.text_view = Gtk.TextView()
            self.text_view.set_monospace(True)
            self.text_view.set_left_margin(10)
            self.text_view.set_right_margin(10)
            self.text_view.set_top_margin(10)
            scroll.set_child(self.text_view)
            
            main_box.append(scroll)
            
            # Status bar
            self.status = Gtk.Label(label="Ready")
            self.status.set_halign(Gtk.Align.START)
            self.status.set_margin_start(10)
            self.status.set_margin_end(10)
            self.status.set_margin_top(5)
            self.status.set_margin_bottom(5)
            main_box.append(self.status)
            
            window.set_child(main_box)
            window.present()
            
            self.window = window
        
        def on_new(self, button):
            self.text_view.get_buffer().set_text("")
            self.current_file = None
            self.window.set_title("Text Editor - Untitled")
            self.status.set_text("New file")
        
        def on_open(self, button):
            dialog = Gtk.FileDialog()
            dialog.open(self.window, None, self._on_open_response)
        
        def _on_open_response(self, dialog, result):
            try:
                file = dialog.open_finish(result)
                if file:
                    path = file.get_path()
                    with open(path, 'r') as f:
                        content = f.read()
                    self.text_view.get_buffer().set_text(content)
                    self.current_file = path
                    self.window.set_title(f"Text Editor - {os.path.basename(path)}")
                    self.status.set_text(f"Opened: {path}")
            except Exception as e:
                self.status.set_text(f"Error: {e}")
        
        def on_save(self, button):
            if self.current_file:
                self._save_file(self.current_file)
            else:
                dialog = Gtk.FileDialog()
                dialog.save(self.window, None, self._on_save_response)
        
        def _on_save_response(self, dialog, result):
            try:
                file = dialog.save_finish(result)
                if file:
                    self._save_file(file.get_path())
            except Exception as e:
                self.status.set_text(f"Error: {e}")
        
        def _save_file(self, path):
            try:
                buffer = self.text_view.get_buffer()
                start = buffer.get_start_iter()
                end = buffer.get_end_iter()
                content = buffer.get_text(start, end, True)
                
                with open(path, 'w') as f:
                    f.write(content)
                
                self.current_file = path
                self.window.set_title(f"Text Editor - {os.path.basename(path)}")
                self.status.set_text(f"Saved: {path}")
            except Exception as e:
                self.status.set_text(f"Error: {e}")


def main():
    if HAS_GTK:
        app = TextEditor()
        return app.run(sys.argv)
    else:
        print("GTK not available, use a terminal editor instead")
        return 1


if __name__ == '__main__':
    sys.exit(main() or 0)
