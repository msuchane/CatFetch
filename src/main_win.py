#!/usr/bin/env python3

from pprint import pprint
from threading import Thread

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk, GLib

import youtube_dl
import basic_functions as bf
from basic_functions import _
import ytdl_wrapper as yw
from downloadables import Downloadable

class MainWindow(Gtk.Window):
    """
    Main application window; contains a ListBox showing videos to be downloaded,
    a 'Paste from Clipboard' button and a 'Download All' button.
    """

    def __init__(self):
        Gtk.Window.__init__(self, title=_("Video Downloader"))

        # a list containing one dictionary per video entered by the user
        # structure:
        # [
        #  {
        #   "url":              "https://...",
        #   "ytdl_info_dict":   <dict>,
        #   "listbox_row":      a <ListBoxRow> instance,
        #   "status":           "waiting" or "downloaded" or "downloading"
        #  }
        # ]
        self.items_list = []

        # For pasting video address
        self.clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)

        self.set_default_size(400, 400)
        self.set_border_width(10)

        self.headerbar = Gtk.HeaderBar()
        self.headerbar.set_show_close_button(True)
        self.headerbar.props.title = _("Video Downloader")
        self.set_titlebar(self.headerbar)

        # The Paste button
        self.paste_button = Gtk.Button(_("Paste"))
        self.paste_button.connect("clicked", self.url_pasted)
        self.paste_button.props.tooltip_text = \
            _("Paste video address from the clipboard")
        self.headerbar.pack_start(self.paste_button)

        # The Download button
        # possible icons: document-save, go-down, emblem-downloads
        self.download_button = Gtk.Button.new_from_icon_name(
            "document-save-symbolic", Gtk.IconSize.BUTTON)
        self.download_button.connect("clicked", self.launch_download)
        self.download_button.props.sensitive = False
        self.download_button.props.tooltip_text = \
            _("Download all waiting videos")
        self.headerbar.pack_end(self.download_button)

        # Button for clearing the videos list
        # TODO: Decide and implement the actual function
        # (should this remove only downloaded videos or all?)
        # Possible icons: mail-mark-junk, edit-delete, window-close, user-trash
        self.clear_button = Gtk.Button.new_from_icon_name(
            "user-trash-symbolic", Gtk.IconSize.BUTTON)
        self.clear_button.connect("clicked", self.clear_vid_list)
        self.clear_button.props.tooltip_text = \
            _("Clear the list")
        self.clear_button.props.sensitive = False
        self.headerbar.pack_end(self.clear_button)

        # This is a general outer box; it is not useful now but may be later.
        # Also may be deleted if I feel like it.
        self.outer_box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL, spacing=10
        )
        self.add(self.outer_box)

        # Let the main content be scrollable
        self.scroll_envelope = Gtk.ScrolledWindow()
        # Show scrollbar for vertical direction if needed. Never show
        # horizontal scrollbar.
        self.scroll_envelope.set_policy(Gtk.PolicyType.NEVER,
                                        Gtk.PolicyType.AUTOMATIC)
        self.outer_box.pack_start(self.scroll_envelope, 1, 1, 0)

        # a placeholder if there aren't any videos to show
        # TODO: find out why this doesn't work or find a different way
        listbox_placeholder = Gtk.Label(
            _("Paste videos from the clipboard using the 'Paste' button"))

        # a ListBox containing added videos to be downloaded
        self.downloadables_listbox = Gtk.ListBox()
        self.downloadables_listbox.set_placeholder(listbox_placeholder)
        # Make rows non-selectable
        self.downloadables_listbox.props.selection_mode = \
            Gtk.SelectionMode.NONE
        self.scroll_envelope.add(self.downloadables_listbox)


    def launch_download(self, widget):
        """ Starts downloading all yet-to-be-downloaded videos in list """

        # Simply execute the download method of each row instance
        # This is already threaded
        for item in self.items_list:
            item["listbox_row"].download_item(widget)

    def url_pasted(self, widget):
        """
        Gets text from the clipboard (if not empty) and hands it over
        to the 'self.url_evaluate' function.
        """

        self.paste_button.props.sensitive = False

        text = self.clipboard.wait_for_text()

        if text != None:
            # self.url_evaluate(text)
            thread = Thread(target=self.url_evaluate, args=(text,))
            thread.daemon = True
            thread.start()
        else:
            print(_("No text in the clipboard!"))
            self.paste_button.props.sensitive = True

    def url_evaluate(self, text):
        """
        Checks if the text if a valid youtube_dl video address and if so,
        extracts info from it to the 'self.items_list' list of dicts
        and launches further functions for adding the video.
        """

        # self.url_entry.set_progress_fraction(0.4)
        # self.url_entry.props.sensitive = False
        # url_entered = self.url_entry.props.text
        url_entered = text

        try:
            ytdl_info_dict = yw.extract_vid_info(url_entered)
            # pprint(self.ytdl_info_dict)
        except youtube_dl.utils.DownloadError as ytdl_msg:
            # Slicing off the initial 18 characters from exception here because
            # the messages's beginning is just a general 'ERROR' text
            # with red-color formatting which doesn't translate nicely
            # into non-terminal output anyway.
            error_msg = "{}".format(ytdl_msg)[18:]
            # Show an error dialog
            GLib.idle_add(self.invalid_url_dialog, url_entered, error_msg)
            # Make Paste button sensitive
            self.paste_button.props.sensitive = True
            return

        # youtube_dl falls back on 'Generic' extractor if the website
        # may contain a video but it is not accessible in the standard way.
        # It could produce valid download; on the other hand, it will
        # happily process a JPEG from an image hosting site. At least
        # for now, let's just ignore the output and treat it as an error.
        if ytdl_info_dict["extractor_key"] == "Generic":
            error_msg = _(''.join(
                ["This address may be a direct video link but also ",
                 "may not. Guessing could lead to bad results. ",
                 "Better download it using another application."]))
            GLib.idle_add(self.invalid_url_dialog, url_entered, error_msg)
            self.paste_button.props.sensitive = True
            return

        # Register the extracted information globally
        # The retrieved information can contain a single video or a playlist.
        # If it's a playlist, add all contained videos:
        if "_type" in ytdl_info_dict and ytdl_info_dict["_type"] == "playlist":

            for each_entry_dict in ytdl_info_dict["entries"]:
                self.add_new_video(each_entry_dict)

        # If it's just a regular video, add it:
        else:
            self.add_new_video(ytdl_info_dict)

        self.download_button.props.sensitive = True
        self.paste_button.props.sensitive = True

    def add_new_video(self, ytdl_info_dict):
        """
        Adds extracted video info to the global list. Then proceeds with
        the 'add_listbox_row' function which creates a new visible row for
        the current video.
        """
        url = ytdl_info_dict["webpage_url"]

        formats_list = ytdl_info_dict["formats"]

        # Build lists containing audio-only, video-only and a/v format options
        available_a_v_s = [av for av in formats_list if bf.is_both_a_v(av)]
        available_video_s = [v for v in formats_list if bf.is_video_only(v)]
        available_audio_s = [a for a in formats_list if bf.is_audio_only(a)]

        self.items_list.append({
            "url": url,
            "ytdl_info_dict": ytdl_info_dict,
            "available_a_v_s": available_a_v_s,
            "available_video_s": available_video_s,
            "available_audio_s": available_audio_s,
            "status": "waiting"
        })

        # Add a new row to the videos list
        # This must be done in a GTK-specific threading way
        GLib.idle_add(self.add_listbox_row, self.items_list[-1])

    def add_listbox_row(self, downloadable_item_dict):
        """
        Creates a ListBoxRow -- a new item showing selected video information
        and options; adds it to the main windows ListBox.
        Should be called in a non-blocking way.
        """

        listbox_row = Downloadable(self, downloadable_item_dict)
        downloadable_item_dict["listbox_row"] = listbox_row
        self.downloadables_listbox.add(listbox_row)
        self.downloadables_listbox.show_all()

    def downloadables_refresh(self, items_list):
        self.outer_box.remove(self.downloadables_listbox)
        self.downloadables_listbox = Gtk.ListBox()

        for item in items_list:
            pprint(item["listbox_row"])
            self.downloadables_listbox.add(item.get("listbox_row"))

        self.outer_box.add(self.downloadables_listbox)
        self.downloadables_listbox.show_all()

    def invalid_url_dialog(self, url, error_msg):
        """ Error window if clipboard text isn't a valid video address """

        text = ''.join(
            [_("The address you entered is not downloadable:"),
             "\n\n",
             "{}\n\n".format(error_msg),
             _("Address: \"{}\"".format(url))])

        dialog = Gtk.MessageDialog(
            self, 0, Gtk.MessageType.ERROR,
            Gtk.ButtonsType.CANCEL, _("Invalid address")
        )
        dialog.format_secondary_text(text)
        dialog.run()
        dialog.destroy()

    def clear_vid_list(self):
        """ Placeholder; see self.clear_button """
        print("cleared")

    def dir_chooser(self, listbox_row):
        """
        A simple filechooser to select the directory where the video file
        should be saved
        """
        dialog = Gtk.FileChooserDialog(
            _("Select where to save the file:"), self,
            Gtk.FileChooserAction.SELECT_FOLDER,
            (Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
             _("Select"), Gtk.ResponseType.OK)
        )

        dialog.set_default_size(400, 400)

        response = dialog.run()

        if response == Gtk.ResponseType.OK:
            location = dialog.get_filename()
            listbox_row.selected_download_dir = location
        else:
            # Cancel clicked
            pass

        dialog.destroy()



if __name__ == "__main__":
    main_win = MainWindow()
    main_win.connect("delete-event", Gtk.main_quit)
    main_win.show_all()
    Gtk.main()
