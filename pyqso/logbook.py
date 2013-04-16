#!/usr/bin/env python 
# File: logbook.py

#    Copyright (C) 2012 Christian Jacobs.

#    This file is part of PyQSO.

#    PyQSO is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    PyQSO is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with PyQSO.  If not, see <http://www.gnu.org/licenses/>.

from gi.repository import Gtk, GObject
import logging
import sys
import sqlite3 as sqlite
from os.path import basename

from adif import *
from log import *
from new_log_dialog import *

class Logbook(Gtk.Notebook):
   ''' A Logbook object can store multiple Log objects. '''
   
   def __init__(self, root_window, path):

      Gtk.Notebook.__init__(self)

      self.root_window = root_window            

      # A stack of Log objects
      self.logs = []
      # SQL database connection to the Logbook's data source
      self.connection = self._connect(path)
      
      # For rendering the logs. One treeview and one treeselection per Log.
      self.treeview = []
      self.treeselection = []

      self._create_new_log_tab()

      # FIXME: This is an unfortunate work-around. If the area around the "+/New Log" button
      # is clicked, PyQSO will change to an empty page. This signal is used to stop this from happening. 
      self.connect("switch-page", self._on_switch_page)

      self.show_all()

      logging.debug("New Logbook instance created!")
      
   def _connect(self, path):
      try:
         connection = sqlite.connect(path)
         return connection
      except sqlite.Error as e:
         logging.exception(e)
         sys.exit(1) # PyQSO can't connect to the database. This error is fatal.
         return None
         
   def _disconnect(self):
      if(self.connection):
         try:
            self.connection.close()
            return True
         except sqlite.Error as e:
            logging.exception(e)
            return False
      else:
         logging.error("Already disconnected. Nothing to do here.")
         return True

   def _create_new_log_tab(self):
      # Create a blank page in the Notebook for the "+" (New Log) tab
      blank_treeview = Gtk.TreeView([])
      # Allow the Log to be scrolled up/down
      sw = Gtk.ScrolledWindow()
      sw.set_shadow_type(Gtk.ShadowType.ETCHED_IN)
      sw.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
      sw.add(blank_treeview)
      vbox = Gtk.VBox()
      vbox.pack_start(sw, True, True, 0)

      # Add a "+" button to the tab
      hbox = Gtk.HBox(False, 0)
      icon = Gtk.Image.new_from_stock(Gtk.STOCK_ADD, Gtk.IconSize.MENU)
      button = Gtk.Button()
      button.set_relief(Gtk.ReliefStyle.NONE)
      button.set_focus_on_click(False)
      button.connect("clicked", self.new_log)
      button.add(icon)
      hbox.pack_start(button, False, False, 0)
      hbox.show_all()
      vbox.show_all()

      self.insert_page(vbox, hbox, 0)

      return

   def _on_switch_page(self, widget, label, new_page):
      if(new_page == self.get_n_pages()-1): # The last (right-most) tab is the "New Log" tab.
         self.stop_emission("switch-page")
      return

   def new_log(self, widget=None):

      exists = True
      dialog = NewLogDialog(self.root_window)
      while(exists):
         response = dialog.run()
         if(response == Gtk.ResponseType.OK):
            log_name = dialog.get_log_name()
            if(not self.log_name_exists(log_name) and log_name != ""):
               l = Log(self.connection, log_name) # Empty log
               self.logs.append(l)
               self.render_log(self.get_number_of_logs()-1)
               exists = False
            else:
               logging.error("Log with name %s already exists." % log_name)
               # Data is not valid - inform the user.
               message = Gtk.MessageDialog(self.root_window, Gtk.DialogFlags.DESTROY_WITH_PARENT,
                                    Gtk.MessageType.ERROR, Gtk.ButtonsType.OK, 
                                    "Log with name %s already exists. Please choose another name." % log_name)
               message.run()
               message.destroy()
         else:
            dialog.destroy()
            return

      dialog.destroy()

      self.set_current_page(self.get_number_of_logs()-1)
      return

   def delete_log(self, widget):
      current = self.get_current_page() - 1 # Gets the index of the selected tab in the logbook
      if(current == -1):
         logging.debug("No logs to delete!")
         return
      log = self.logs[current]

      dialog = Gtk.MessageDialog(self.root_window, Gtk.DialogFlags.DESTROY_WITH_PARENT,
                              Gtk.MessageType.QUESTION, Gtk.ButtonsType.YES_NO, 
                              "Are you sure you want to delete log %s?" % log.name)
      response = dialog.run()
      dialog.destroy()
      if(response == Gtk.ResponseType.YES):
         self.logs.pop(current)
         # Remove the log from the renderers too
         self.treeview.pop(current)
         self.treeselection.pop(current)
         # And finally remove the tab in the Logbook
         self.remove_page(current)

      return

   def render_log(self, index):
      # Render the Log
      #sorter = Gtk.TreeModelSort(model=log) #FIXME: Get sorted columns working!
      #sorter.set_sort_column_id(1, Gtk.SortType.ASCENDING)
      #self.treeview.append(Gtk.TreeView(sorter))
      self.treeview.append(Gtk.TreeView(self.logs[index]))
      self.treeview[index].set_grid_lines(Gtk.TreeViewGridLines.BOTH)
      self.treeview[index].connect("row-activated", self.edit_record_callback, self.root_window)
      self.treeselection.append(self.treeview[index].get_selection())
      self.treeselection[index].set_mode(Gtk.SelectionMode.SINGLE)
      # Allow the Log to be scrolled up/down
      sw = Gtk.ScrolledWindow()
      sw.set_shadow_type(Gtk.ShadowType.ETCHED_IN)
      sw.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
      sw.add(self.treeview[index])
      vbox = Gtk.VBox()
      vbox.pack_start(sw, True, True, 0)

      # Add a close button to the tab
      hbox = Gtk.HBox(False, 0)
      label = Gtk.Label(self.logs[index].name)
      hbox.pack_start(label, False, False, 0)
      icon = Gtk.Image.new_from_stock(Gtk.STOCK_CLOSE, Gtk.IconSize.MENU)
      button = Gtk.Button()
      button.set_relief(Gtk.ReliefStyle.NONE)
      button.set_focus_on_click(False)
      button.connect("clicked", self.delete_log)
      button.add(icon)
      hbox.pack_start(button, False, False, 0)
      hbox.show_all()

      self.insert_page(vbox, hbox, index) # Append the new log as a new tab

      # The first column of the logbook will always be the unique record index.
      # Let's append this separately to the field names.
      renderer = Gtk.CellRendererText()
      column = Gtk.TreeViewColumn("Index", renderer, text=0)
      column.set_resizable(True)
      column.set_min_width(50)
      self.treeview[index].append_column(column)
         
      # Set up column names for each selected field
      field_names = self.logs[index].SELECTED_FIELD_NAMES_ORDERED
      for i in range(0, len(field_names)):
         renderer = Gtk.CellRendererText()
         column = Gtk.TreeViewColumn(self.logs[index].SELECTED_FIELD_NAMES_FRIENDLY[field_names[i]], renderer, text=i+1)
         column.set_resizable(True)
         column.set_min_width(50)
         self.treeview[index].append_column(column)

      self.show_all()


   def import_log(self, widget):
      dialog = Gtk.FileChooserDialog("Import ADIF Log File",
                                    None,
                                    Gtk.FileChooserAction.OPEN,
                                    (Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
                                    Gtk.STOCK_OPEN, Gtk.ResponseType.OK))
      filter = Gtk.FileFilter()
      filter.set_name("All ADIF files")
      filter.add_pattern("*.adi")
      dialog.add_filter(filter)
      
      response = dialog.run()
      if(response == Gtk.ResponseType.OK):
         path = dialog.get_filename()
      else:
         path = None
      dialog.destroy()
      
      if(path is None):
         logging.debug("No file path specified.")
         return

      for log in self.logs:
         if(log.path == path):
            dialog = Gtk.MessageDialog(self.root_window, Gtk.DialogFlags.DESTROY_WITH_PARENT,
                                 Gtk.MessageType.ERROR, Gtk.ButtonsType.OK, 
                                 "Log %s is already open." % path)
            response = dialog.run()
            dialog.destroy()
            return
      
      adif = ADIF()
      records = adif.read(path)
      
      l = Log(records, path, basename(path))
      self.logs.append(l)
      self.render_log(l)
      
      return
      
   def export_log(self, widget=None):

      current = self.get_current_page() # Gets the index of the selected tab in the logbook
      if(current == -1):
         logging.debug("No log files to export!")
         return

      log = self.logs[current]

      dialog = Gtk.FileChooserDialog("Export Log to File",
                              None,
                              Gtk.FileChooserAction.SAVE,
                              (Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
                              Gtk.STOCK_SAVE, Gtk.ResponseType.OK))
                                 
      response = dialog.run()
      if(response == Gtk.ResponseType.OK):
         path = dialog.get_filename()
      else:
         path = None
      dialog.destroy()
         
      if(path is None):
         logging.debug("No file path specified.")
         return

      adif = ADIF()
      adif.write(log.records, path)

      if(log.modified):
         log.path = path
         log.name = basename(log.path)
         self.set_tab_label_text(self.get_nth_page(current), log.name)
         log.set_modified(False)
      return

   def add_record_callback(self, widget):

      current = self.get_current_page() - 1 # Gets the index of the selected tab in the logbook
      if(current == -1):
         logging.debug("Tried to add a record, but no log present!")
         return
      log = self.logs[current]
      dialog = RecordDialog(root_window=self.root_window, log=log, index=None)
      all_valid = False # Are all the field entries valid?

      while(not all_valid): 
         # This while loop gives the user infinite attempts at giving valid data.
         # The add/edit record window will stay open until the user gives valid data,
         # or until the Cancel button is clicked.
         all_valid = True
         response = dialog.run() #FIXME: Is it ok to call .run() multiple times on the same RecordDialog object?
         if(response == Gtk.ResponseType.OK):
            fields_and_data = {}
            field_names = log.SELECTED_FIELD_NAMES_ORDERED
            for i in range(0, len(field_names)):
               #TODO: Validate user input!
               fields_and_data[field_names[i]] = dialog.get_data(field_names[i])
               if(not(dialog.is_valid(field_names[i], fields_and_data[field_names[i]], log.SELECTED_FIELD_NAMES_TYPES[field_names[i]]))):
                  # Data is not valid - inform the user.
                  message = Gtk.MessageDialog(self.root_window, Gtk.DialogFlags.DESTROY_WITH_PARENT,
                                    Gtk.MessageType.ERROR, Gtk.ButtonsType.OK, 
                                    "The data in field \"%s\" is not valid!" % field_names[i])
                  message.run()
                  message.destroy()
                  all_valid = False
                  break # Don't check the other data until the user has fixed the current one.

            if(all_valid):
               # All data has been validated, so we can go ahead and add the new record.
               log_entry = [log.get_number_of_records()] # Add the next available record index
               field_names = log.SELECTED_FIELD_NAMES_ORDERED
               for i in range(0, len(field_names)):
                  log_entry.append(fields_and_data[field_names[i]])
               log.append(log_entry)
               log.add_record(fields_and_data)
               # Select the new Record's row in the treeview.
               self.treeselection[current].select_path(log.get_number_of_records()-1)
               self.set_tab_label_text(self.get_nth_page(current), log.name)

      dialog.destroy()
      return
      
   def delete_record_callback(self, widget):
      current = self.get_current_page() - 1 # Get the selected log
      if(current == -1):
         logging.debug("Tried to delete a record, but no log present!")
         return
      (model, path) = self.treeselection[current].get_selected_rows() # Get the selected row in the log
      try:
         iter = model.get_iter(path[0])
         index = model.get_value(iter,0)
      except IndexError:
         logging.debug("Trying to delete a record, but there are no records in the log!")
         return

      dialog = Gtk.MessageDialog(self.root_window, Gtk.DialogFlags.DESTROY_WITH_PARENT,
                                 Gtk.MessageType.QUESTION, Gtk.ButtonsType.YES_NO, 
                                 "Are you sure you want to delete record %d?" % index)
      response = dialog.run()
      if(response == Gtk.ResponseType.YES):
         # Deletes the record with index 'index' from the Records list.
         # 'iter' is needed to remove the record from the ListStore itself.
         self.logs[current].delete_record(index, iter)
         
      dialog.destroy()
      self.set_tab_label_text(self.get_nth_page(current), self.logs[current].name)
      return

   def edit_record_callback(self, widget, path, view_column):
      # Note: the path and view_column arguments need to be passed in
      # since they associated with the row-activated signal.

      current = self.get_current_page() - 1 # Get the selected log
      if(current == -1):
         logging.debug("Tried to edit a record, but no log present!")
         return
      
      log = self.logs[current]

      (model, path) = self.treeselection[current].get_selected_rows() # Get the selected row in the log
      try:
         iter = model.get_iter(path[0])
         row_index = model.get_value(iter,0)
      except IndexError:
         logging.debug("Could not find the selected row's index!")
         return

      dialog = RecordDialog(root_window=self.root_window, log=self.logs[current], index=row_index)
      all_valid = False # Are all the field entries valid?

      while(not all_valid): 
         # This while loop gives the user infinite attempts at giving valid data.
         # The add/edit record window will stay open until the user gives valid data,
         # or until the Cancel button is clicked.
         all_valid = True
         response = dialog.run() #FIXME: Is it ok to call .run() multiple times on the same RecordDialog object?
         if(response == Gtk.ResponseType.OK):
            fields_and_data = {}
            field_names = self.logs[current].SELECTED_FIELD_NAMES_ORDERED
            for i in range(0, len(field_names)):
               #TODO: Validate user input!
               fields_and_data[field_names[i]] = dialog.get_data(field_names[i])
               if(not(dialog.is_valid(field_names[i], fields_and_data[field_names[i]], self.logs[current].SELECTED_FIELD_NAMES_TYPES[field_names[i]]))):
                  # Data is not valid - inform the user.
                  message = Gtk.MessageDialog(self.root_window, Gtk.DialogFlags.DESTROY_WITH_PARENT,
                                    Gtk.MessageType.ERROR, Gtk.ButtonsType.OK, 
                                    "The data in field \"%s\" is not valid!" % field_names[i])
                  message.run()
                  message.destroy()
                  all_valid = False
                  break # Don't check the other data until the user has fixed the current one.

            if(all_valid):
               for i in range(0, len(field_names)):
                  # All data has been validated, so we can go ahead and update the record.
                  # First update the Record object... 
                  log.edit_record(row_index, field_names[i], fields_and_data[field_names[i]])
                  # ...and then the Logbook.
                  # (we add 1 onto the column_index here because we don't want to consider the index column)
                  log[row_index][i+1] = fields_and_data[field_names[i]]
                  self.set_tab_label_text(self.get_nth_page(current), log.name)

      dialog.destroy()
      return

   def search_log_callback(self, widget):
      print "Search feature has not yet been implemented."

   def get_number_of_logs(self):
      return len(self.logs)

   def log_name_exists(self, table_name):
      with self.connection:
         c = self.connection.cursor()
         c.execute("SELECT name FROM sqlite_master WHERE type='table'")
         names = c.fetchall()
      for name in names:
         if(table_name in name):
            return True
      return False

