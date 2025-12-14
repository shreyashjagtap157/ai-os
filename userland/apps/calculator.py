#!/usr/bin/env python3
"""
AI-OS Calculator
Simple calculator application.
"""

import sys

try:
    import gi
    gi.require_version('Gtk', '4.0')
    from gi.repository import Gtk
    HAS_GTK = True
except ImportError:
    HAS_GTK = False


if HAS_GTK:
    class Calculator(Gtk.Application):
        def __init__(self):
            super().__init__(application_id='com.aios.calculator')
            self.expression = ""
        
        def do_activate(self):
            window = Gtk.ApplicationWindow(application=self, title="Calculator")
            window.set_default_size(300, 400)
            
            main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
            main_box.set_margin_top(16)
            main_box.set_margin_bottom(16)
            main_box.set_margin_start(16)
            main_box.set_margin_end(16)
            
            # Display
            self.display = Gtk.Entry()
            self.display.set_text("0")
            self.display.set_alignment(1)
            self.display.set_editable(False)
            self.display.add_css_class('display')
            main_box.append(self.display)
            
            # Buttons
            buttons = [
                ['C', '(', ')', '/'],
                ['7', '8', '9', '*'],
                ['4', '5', '6', '-'],
                ['1', '2', '3', '+'],
                ['0', '.', '±', '='],
            ]
            
            for row in buttons:
                row_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
                row_box.set_homogeneous(True)
                
                for label in row:
                    btn = Gtk.Button(label=label)
                    btn.connect('clicked', self.on_button_click, label)
                    row_box.append(btn)
                
                main_box.append(row_box)
            
            window.set_child(main_box)
            window.present()
        
        def on_button_click(self, button, label):
            if label == 'C':
                self.expression = ""
                self.display.set_text("0")
            elif label == '=':
                try:
                    result = eval(self.expression)
                    self.display.set_text(str(result))
                    self.expression = str(result)
                except:
                    self.display.set_text("Error")
                    self.expression = ""
            elif label == '±':
                if self.expression.startswith('-'):
                    self.expression = self.expression[1:]
                else:
                    self.expression = '-' + self.expression
                self.display.set_text(self.expression or "0")
            else:
                self.expression += label
                self.display.set_text(self.expression)


def main():
    if HAS_GTK:
        app = Calculator()
        return app.run(sys.argv)
    else:
        print("GTK not available")
        # CLI fallback
        print("Calculator CLI")
        while True:
            try:
                expr = input(">>> ")
                if expr.lower() in ('exit', 'quit'):
                    break
                print(eval(expr))
            except (KeyboardInterrupt, EOFError):
                break
            except Exception as e:
                print(f"Error: {e}")


if __name__ == '__main__':
    sys.exit(main() or 0)
