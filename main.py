import os
import threading
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from pathlib import Path

from PIL import Image, ImageTk

import config
import database
import ocr_engine
import scanner

# Configuration
THUMBNAIL_SIZE = (120, 120)
PREVIEW_SIZE = (500, 500)
COLUMNS = 4
MAX_SNIPPET_LENGTH = 60

# Theme colors
THEMES = {
    "light": {
        "bg": "#f5f5f5",
        "fg": "#1a1a1a",
        "entry_bg": "#ffffff",
        "entry_fg": "#1a1a1a",
        "canvas_bg": "#ffffff",
        "text_bg": "#ffffff",
        "text_fg": "#1a1a1a",
        "button_bg": "#e0e0e0",
        "highlight": "#0078d4",
        "border": "#cccccc",
    },
    "dark": {
        "bg": "#1e1e1e",
        "fg": "#d4d4d4",
        "entry_bg": "#2d2d2d",
        "entry_fg": "#d4d4d4",
        "canvas_bg": "#252526",
        "text_bg": "#1e1e1e",
        "text_fg": "#d4d4d4",
        "button_bg": "#3c3c3c",
        "highlight": "#007acc",
        "border": "#3c3c3c",
    }
}


class ScreenshotSearchApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Screenshot Search")

        # Store image references to prevent garbage collection
        self.thumbnail_refs = []
        self.preview_image_ref = None

        # Currently selected result
        self.selected_result = None

        # Scanning state
        self.is_scanning = False

        # Layout mode
        self.layout = config.get_layout()

        # Main content container (will be rebuilt on layout change)
        self.main_content = None

        # Theme
        self.theme = config.get_theme()

        # Settings window reference (for theme updates)
        self.settings_window = None

        # Set window size based on layout
        if self.layout == "side_panel":
            self.root.geometry("1100x700")
            self.root.minsize(900, 500)
        else:
            self.root.geometry("800x600")
            self.root.minsize(600, 400)

        # Initialize database
        database.init_db()

        # Check Tesseract
        if not ocr_engine.is_tesseract_available():
            messagebox.showwarning(
                "Tesseract Not Found",
                "Tesseract OCR is not installed or not in PATH.\n\n"
                "Please install from:\n"
                "https://github.com/UB-Mannheim/tesseract/wiki\n\n"
                "The app will still work for searching already-indexed screenshots."
            )

        self.setup_ui()
        self.apply_theme()
        self.update_status()
        self.load_folders()

        # Check for first-run setup
        if not config.is_configured():
            self.root.after(100, self.show_first_run_setup)

    def setup_ui(self):
        # Top frame - search and controls
        top_frame = ttk.Frame(self.root, padding="10")
        top_frame.pack(fill=tk.X)

        # Search entry
        ttk.Label(top_frame, text="Search:").pack(side=tk.LEFT)
        self.search_var = tk.StringVar()
        self.search_entry = ttk.Entry(top_frame, textvariable=self.search_var, width=30)
        self.search_entry.pack(side=tk.LEFT, padx=(5, 10))
        self.search_entry.bind('<Return>', lambda e: self.do_search())

        # Search button
        self.search_btn = ttk.Button(top_frame, text="Search", command=self.do_search)
        self.search_btn.pack(side=tk.LEFT, padx=(0, 20))

        # Date filter
        ttk.Label(top_frame, text="Date:").pack(side=tk.LEFT)
        self.date_filter_var = tk.StringVar(value="All Time")
        self.date_filter = ttk.Combobox(
            top_frame,
            textvariable=self.date_filter_var,
            values=["All Time", "Today", "Last 7 Days", "Last 30 Days", "Last Year"],
            state="readonly",
            width=12
        )
        self.date_filter.pack(side=tk.LEFT, padx=(5, 15))

        # Folder filter
        ttk.Label(top_frame, text="Folder:").pack(side=tk.LEFT)
        self.folder_filter_var = tk.StringVar(value="All Folders")
        self.folder_filter = ttk.Combobox(
            top_frame,
            textvariable=self.folder_filter_var,
            values=["All Folders"],
            state="readonly",
            width=15
        )
        self.folder_filter.pack(side=tk.LEFT, padx=(5, 15))

        # Scan button
        self.scan_btn = ttk.Button(top_frame, text="Scan Now", command=self.start_scan)
        self.scan_btn.pack(side=tk.RIGHT)

        # Settings button
        self.settings_btn = ttk.Button(top_frame, text="Settings", command=self.show_settings)
        self.settings_btn.pack(side=tk.RIGHT, padx=(0, 5))

        # Status frame
        status_frame = ttk.Frame(self.root, padding="10 5")
        status_frame.pack(fill=tk.X)

        self.status_var = tk.StringVar(value="Ready")
        self.status_label = ttk.Label(status_frame, textvariable=self.status_var)
        self.status_label.pack(side=tk.LEFT)

        # Progress bar (hidden by default)
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(
            status_frame, variable=self.progress_var, maximum=100, length=200
        )

        # Build layout based on setting
        if self.layout == "side_panel":
            self.setup_side_panel_layout()
        else:
            self.setup_popup_layout()

    def setup_popup_layout(self):
        """Simple layout - just results grid, click opens popup."""
        results_container = ttk.Frame(self.root)
        results_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        # Store reference for layout switching
        self.main_content = results_container

        # Canvas for scrollable results
        self.canvas = tk.Canvas(results_container)
        scrollbar = ttk.Scrollbar(results_container, orient=tk.VERTICAL, command=self.canvas.yview)

        self.results_frame = ttk.Frame(self.canvas)

        self.canvas.configure(yscrollcommand=scrollbar.set)

        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.canvas_window = self.canvas.create_window((0, 0), window=self.results_frame, anchor=tk.NW)

        # Bind events for scrolling
        self.results_frame.bind('<Configure>', self.on_frame_configure)
        self.canvas.bind('<Configure>', self.on_canvas_configure)
        self.canvas.bind_all('<MouseWheel>', self.on_mousewheel)

    def setup_side_panel_layout(self):
        """Split layout with results on left, preview on right."""
        main_pane = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        main_pane.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        # Store reference for layout switching
        self.main_content = main_pane

        # Left side - Results grid
        results_container = ttk.Frame(main_pane)
        main_pane.add(results_container, weight=2)

        # Canvas for scrollable results
        self.canvas = tk.Canvas(results_container)
        scrollbar = ttk.Scrollbar(results_container, orient=tk.VERTICAL, command=self.canvas.yview)

        self.results_frame = ttk.Frame(self.canvas)

        self.canvas.configure(yscrollcommand=scrollbar.set)

        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.canvas_window = self.canvas.create_window((0, 0), window=self.results_frame, anchor=tk.NW)

        # Bind events for scrolling
        self.results_frame.bind('<Configure>', self.on_frame_configure)
        self.canvas.bind('<Configure>', self.on_canvas_configure)
        self.canvas.bind_all('<MouseWheel>', self.on_mousewheel)

        # Right side - Preview pane
        preview_container = ttk.LabelFrame(main_pane, text="Preview", padding="10")
        main_pane.add(preview_container, weight=1)

        # Preview image
        self.preview_label = ttk.Label(preview_container, text="Click a thumbnail to preview", anchor=tk.CENTER)
        self.preview_label.pack(fill=tk.BOTH, expand=True)

        # Preview buttons frame
        preview_buttons = ttk.Frame(preview_container)
        preview_buttons.pack(fill=tk.X, pady=(10, 5))

        self.copy_btn = ttk.Button(preview_buttons, text="Copy Text", command=self.copy_text, state=tk.DISABLED)
        self.copy_btn.pack(side=tk.LEFT, padx=(0, 5))

        self.open_btn = ttk.Button(preview_buttons, text="Open Image", command=self.open_selected, state=tk.DISABLED)
        self.open_btn.pack(side=tk.LEFT, padx=(0, 5))

        self.folder_btn = ttk.Button(preview_buttons, text="Open Folder", command=self.open_folder, state=tk.DISABLED)
        self.folder_btn.pack(side=tk.LEFT)

        # Text preview with scrollbar
        text_frame = ttk.LabelFrame(preview_container, text="Extracted Text", padding="5")
        text_frame.pack(fill=tk.BOTH, expand=True, pady=(10, 0))

        self.text_preview = tk.Text(text_frame, wrap=tk.WORD, height=8, state=tk.DISABLED)
        text_scrollbar = ttk.Scrollbar(text_frame, orient=tk.VERTICAL, command=self.text_preview.yview)
        self.text_preview.configure(yscrollcommand=text_scrollbar.set)

        text_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.text_preview.pack(fill=tk.BOTH, expand=True)

    def switch_layout(self, new_layout):
        """Switch layout dynamically without restart."""
        if new_layout == self.layout:
            return

        # Clear results and references
        self.thumbnail_refs.clear()
        self.preview_image_ref = None
        self.selected_result = None

        # Destroy current main content
        if self.main_content:
            self.main_content.destroy()

        # Update layout
        self.layout = new_layout
        config.set_layout(new_layout)

        # Adjust window size
        if self.layout == "side_panel":
            self.root.geometry("1100x700")
            self.root.minsize(900, 500)
        else:
            self.root.geometry("800x600")
            self.root.minsize(600, 400)

        # Build new layout
        if self.layout == "side_panel":
            self.setup_side_panel_layout()
        else:
            self.setup_popup_layout()

        # Reapply theme to new widgets
        self.apply_theme()

        self.status_var.set(f"Layout changed to {new_layout.replace('_', ' ')}")

    def apply_theme(self):
        """Apply the current theme to all widgets."""
        colors = THEMES[self.theme]

        # Configure ttk styles
        style = ttk.Style()

        # Use clam as base - it's the most customizable
        style.theme_use('clam')

        # Configure all widget styles
        style.configure(".",
                        background=colors["bg"],
                        foreground=colors["fg"],
                        fieldbackground=colors["entry_bg"],
                        troughcolor=colors["entry_bg"],
                        borderwidth=1)

        style.configure("TFrame", background=colors["bg"])
        style.configure("TLabel", background=colors["bg"], foreground=colors["fg"])

        # Buttons with better styling
        style.configure("TButton",
                        background=colors["button_bg"],
                        foreground=colors["fg"],
                        bordercolor=colors["border"],
                        lightcolor=colors["button_bg"],
                        darkcolor=colors["button_bg"],
                        padding=(10, 5),
                        borderwidth=1,
                        focuscolor=colors["highlight"])
        style.map("TButton",
                  background=[("active", colors["highlight"]),
                              ("pressed", colors["highlight"]),
                              ("disabled", colors["bg"])],
                  foreground=[("active", "#ffffff"),
                              ("disabled", "#666666")],
                  bordercolor=[("active", colors["highlight"])])

        # Entry fields
        style.configure("TEntry",
                        fieldbackground=colors["entry_bg"],
                        foreground=colors["entry_fg"],
                        insertcolor=colors["fg"],
                        bordercolor=colors["border"],
                        lightcolor=colors["border"],
                        darkcolor=colors["border"],
                        borderwidth=1,
                        padding=5)

        # Combobox
        style.configure("TCombobox",
                        fieldbackground=colors["entry_bg"],
                        foreground=colors["entry_fg"],
                        background=colors["button_bg"],
                        arrowcolor=colors["fg"],
                        bordercolor=colors["border"],
                        lightcolor=colors["border"],
                        darkcolor=colors["border"],
                        borderwidth=1,
                        padding=5)
        style.map("TCombobox",
                  fieldbackground=[("readonly", colors["entry_bg"]),
                                   ("disabled", colors["bg"])],
                  foreground=[("readonly", colors["entry_fg"])],
                  background=[("readonly", colors["button_bg"])])

        # Radiobutton
        style.configure("TRadiobutton",
                        background=colors["bg"],
                        foreground=colors["fg"],
                        indicatorbackground=colors["entry_bg"],
                        indicatorforeground=colors["highlight"])
        style.map("TRadiobutton",
                  background=[("active", colors["bg"])],
                  indicatorbackground=[("selected", colors["highlight"])])

        # LabelFrame
        style.configure("TLabelframe",
                        background=colors["bg"],
                        foreground=colors["fg"],
                        bordercolor=colors["border"],
                        lightcolor=colors["border"],
                        darkcolor=colors["border"])
        style.configure("TLabelframe.Label",
                        background=colors["bg"],
                        foreground=colors["fg"])

        # Scrollbar
        style.configure("Vertical.TScrollbar",
                        background=colors["button_bg"],
                        troughcolor=colors["entry_bg"],
                        bordercolor=colors["border"],
                        arrowcolor=colors["fg"],
                        lightcolor=colors["button_bg"],
                        darkcolor=colors["button_bg"])
        style.map("Vertical.TScrollbar",
                  background=[("active", colors["highlight"]),
                              ("pressed", colors["highlight"])])

        # Progress bar
        style.configure("Horizontal.TProgressbar",
                        background=colors["highlight"],
                        troughcolor=colors["entry_bg"],
                        bordercolor=colors["bg"],
                        lightcolor=colors["highlight"],
                        darkcolor=colors["highlight"])

        # PanedWindow
        style.configure("TPanedwindow", background=colors["bg"])

        # Configure root window
        self.root.configure(bg=colors["bg"])

        # Configure canvas if it exists
        if hasattr(self, 'canvas'):
            self.canvas.configure(bg=colors["canvas_bg"], highlightthickness=0)

        # Configure text widgets if they exist (side panel layout)
        if hasattr(self, 'text_preview') and self.text_preview.winfo_exists():
            self.text_preview.configure(
                bg=colors["text_bg"],
                fg=colors["text_fg"],
                insertbackground=colors["fg"]
            )

        # Force update of all widgets
        self.root.update_idletasks()

    def switch_theme(self, new_theme):
        """Switch theme dynamically."""
        if new_theme == self.theme:
            return

        self.theme = new_theme
        config.set_theme(new_theme)
        self.apply_theme()

        # Reopen settings dialog if it was open (to refresh its appearance)
        if self.settings_window and self.settings_window.winfo_exists():
            self.settings_window.destroy()
            self.root.after(50, self.show_settings)

        self.status_var.set(f"Theme changed to {new_theme}")

    def load_folders(self):
        """Load folder list into the dropdown."""
        folders = database.get_folders()
        self.folder_filter['values'] = folders

    def on_frame_configure(self, event):
        self.canvas.configure(scrollregion=self.canvas.bbox('all'))

    def on_canvas_configure(self, event):
        self.canvas.itemconfig(self.canvas_window, width=event.width)

    def on_mousewheel(self, event):
        self.canvas.yview_scroll(int(-1 * (event.delta / 120)), 'units')

    def update_status(self):
        stats = database.get_stats()
        folder = config.get_screenshots_folder()
        if folder:
            folder_name = Path(folder).name
            self.status_var.set(f"Indexed: {stats['total_indexed']} screenshots | Folder: {folder_name}")
        else:
            self.status_var.set(f"Indexed: {stats['total_indexed']} screenshots | No folder configured")

    def get_date_filter_value(self):
        """Convert UI date filter to database parameter."""
        mapping = {
            "All Time": None,
            "Today": "today",
            "Last 7 Days": "week",
            "Last 30 Days": "month",
            "Last Year": "year"
        }
        return mapping.get(self.date_filter_var.get())

    def do_search(self):
        query = self.search_var.get().strip()
        if not query:
            messagebox.showinfo("Search", "Please enter a search term")
            return

        # Clear previous results
        self.clear_results()
        if self.layout == "side_panel":
            self.clear_preview()

        # Get filter values
        date_filter = self.get_date_filter_value()
        folder_filter = self.folder_filter_var.get()

        # Search database with filters
        results = database.search(
            query,
            date_filter=date_filter,
            folder_filter=folder_filter if folder_filter != "All Folders" else None
        )

        if not results:
            self.status_var.set(f"No results for '{query}'")
            return

        self.status_var.set(f"Found {len(results)} results for '{query}'")
        self.display_results(results)

    def clear_results(self):
        for widget in self.results_frame.winfo_children():
            widget.destroy()
        self.thumbnail_refs.clear()

    def clear_preview(self):
        """Clear the side panel preview (only used in side_panel layout)."""
        if self.layout != "side_panel":
            return
        self.selected_result = None
        self.preview_image_ref = None
        self.preview_label.configure(image='', text="Click a thumbnail to preview")
        self.text_preview.configure(state=tk.NORMAL)
        self.text_preview.delete('1.0', tk.END)
        self.text_preview.configure(state=tk.DISABLED)
        self.copy_btn.configure(state=tk.DISABLED)
        self.open_btn.configure(state=tk.DISABLED)
        self.folder_btn.configure(state=tk.DISABLED)

    def display_results(self, results):
        row = 0
        col = 0
        columns = COLUMNS if self.layout == "popup" else 3

        for result in results:
            file_path = result['file_path']
            snippet = result['snippet']

            # Create frame for each result
            item_frame = ttk.Frame(self.results_frame, padding="5")
            item_frame.grid(row=row, column=col, padx=5, pady=5, sticky=tk.N)

            # Create thumbnail
            thumbnail = self.create_thumbnail(file_path)
            if thumbnail:
                self.thumbnail_refs.append(thumbnail)
                thumb_label = ttk.Label(item_frame, image=thumbnail, cursor="hand2")
                thumb_label.pack()
                # Click shows preview (popup or side panel based on layout)
                thumb_label.bind('<Button-1>', lambda e, r=result: self.show_preview(r))
                thumb_label.bind('<Double-Button-1>', lambda e, p=file_path: self.open_image(p))
            else:
                ttk.Label(item_frame, text="[No preview]").pack()

            # Truncate snippet for display
            display_snippet = snippet[:MAX_SNIPPET_LENGTH]
            if len(snippet) > MAX_SNIPPET_LENGTH:
                display_snippet += "..."

            # Replace highlight markers
            display_snippet = display_snippet.replace('>>>', '[').replace('<<<', ']')

            snippet_label = ttk.Label(
                item_frame,
                text=display_snippet,
                wraplength=THUMBNAIL_SIZE[0],
                justify=tk.CENTER
            )
            snippet_label.pack(pady=(5, 0))

            col += 1
            if col >= columns:
                col = 0
                row += 1

    def create_thumbnail(self, file_path: str):
        try:
            if not Path(file_path).exists():
                return None

            image = Image.open(file_path)
            image.thumbnail(THUMBNAIL_SIZE, Image.Resampling.LANCZOS)
            return ImageTk.PhotoImage(image)
        except Exception as e:
            print(f"Failed to create thumbnail for {file_path}: {e}")
            return None

    def show_preview(self, result):
        """Show preview - either popup or side panel based on layout."""
        if self.layout == "side_panel":
            self.show_side_panel_preview(result)
        else:
            self.show_preview_popup(result)

    def show_preview_popup(self, result):
        """Show a popup dialog with the screenshot preview."""
        file_path = result['file_path']
        colors = THEMES[self.theme]

        # Create popup window
        popup = tk.Toplevel(self.root)
        popup.title("Screenshot Preview")
        popup.geometry("600x700")
        popup.transient(self.root)
        popup.configure(bg=colors["bg"])

        # Main frame with padding
        main_frame = ttk.Frame(popup, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Image preview
        image_frame = ttk.Frame(main_frame)
        image_frame.pack(fill=tk.BOTH, expand=True)

        try:
            if Path(file_path).exists():
                image = Image.open(file_path)
                image.thumbnail(PREVIEW_SIZE, Image.Resampling.LANCZOS)
                photo = ImageTk.PhotoImage(image)
                image_label = ttk.Label(image_frame, image=photo)
                image_label.image = photo  # Keep reference
                image_label.pack(expand=True)
            else:
                ttk.Label(image_frame, text="File not found").pack(expand=True)
        except Exception as e:
            ttk.Label(image_frame, text=f"Error loading image: {e}").pack(expand=True)

        # Buttons
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill=tk.X, pady=(10, 5))

        def copy_text():
            text = result.get('extracted_text', '') or database.get_screenshot_text(file_path)
            if text:
                self.root.clipboard_clear()
                self.root.clipboard_append(text)
                self.status_var.set("Text copied to clipboard!")
            else:
                messagebox.showinfo("Copy Text", "No text to copy")

        ttk.Button(btn_frame, text="Copy Text", command=copy_text).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(btn_frame, text="Open Image", command=lambda: self.open_image(file_path)).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(btn_frame, text="Open Folder", command=lambda: os.startfile(Path(file_path).parent)).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(btn_frame, text="Close", command=popup.destroy).pack(side=tk.RIGHT)

        # Text preview
        text_frame = ttk.LabelFrame(main_frame, text="Extracted Text", padding="5")
        text_frame.pack(fill=tk.BOTH, expand=True, pady=(10, 0))

        text_widget = tk.Text(
            text_frame,
            wrap=tk.WORD,
            height=6,
            bg=colors["text_bg"],
            fg=colors["text_fg"],
            insertbackground=colors["fg"]
        )
        text_scrollbar = ttk.Scrollbar(text_frame, orient=tk.VERTICAL, command=text_widget.yview)
        text_widget.configure(yscrollcommand=text_scrollbar.set)

        text_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        text_widget.pack(fill=tk.BOTH, expand=True)

        # Insert text
        text = result.get('extracted_text', '') or database.get_screenshot_text(file_path)
        text_widget.insert('1.0', text if text else "(No text extracted)")
        text_widget.configure(state=tk.DISABLED)

        # File path label
        path_label = ttk.Label(main_frame, text=file_path, foreground="gray")
        path_label.pack(fill=tk.X, pady=(5, 0))

    def show_side_panel_preview(self, result):
        """Show preview in the side panel."""
        file_path = result['file_path']
        self.selected_result = result

        # Enable buttons
        self.copy_btn.configure(state=tk.NORMAL)
        self.open_btn.configure(state=tk.NORMAL)
        self.folder_btn.configure(state=tk.NORMAL)

        # Load and display preview image
        try:
            if Path(file_path).exists():
                image = Image.open(file_path)
                image.thumbnail((400, 400), Image.Resampling.LANCZOS)
                self.preview_image_ref = ImageTk.PhotoImage(image)
                self.preview_label.configure(image=self.preview_image_ref, text='')
            else:
                self.preview_label.configure(image='', text="File not found")
        except Exception as e:
            self.preview_label.configure(image='', text=f"Error: {e}")

        # Display extracted text
        text = result.get('extracted_text', '') or database.get_screenshot_text(file_path)
        self.text_preview.configure(state=tk.NORMAL)
        self.text_preview.delete('1.0', tk.END)
        self.text_preview.insert('1.0', text if text else "(No text extracted)")
        self.text_preview.configure(state=tk.DISABLED)

    def copy_text(self):
        """Copy extracted text to clipboard (side panel layout)."""
        if not self.selected_result:
            return

        text = self.text_preview.get('1.0', tk.END).strip()
        if text and text != "(No text extracted)":
            self.root.clipboard_clear()
            self.root.clipboard_append(text)
            self.status_var.set("Text copied to clipboard!")
        else:
            messagebox.showinfo("Copy Text", "No text to copy")

    def open_selected(self):
        """Open the selected image in default viewer (side panel layout)."""
        if self.selected_result:
            self.open_image(self.selected_result['file_path'])

    def open_folder(self):
        """Open the folder containing the selected image (side panel layout)."""
        if self.selected_result:
            file_path = Path(self.selected_result['file_path'])
            if file_path.exists():
                os.startfile(file_path.parent)
            else:
                messagebox.showerror("Error", "File not found")

    def open_image(self, file_path: str):
        """Open image in default system viewer."""
        if Path(file_path).exists():
            os.startfile(file_path)
        else:
            messagebox.showerror("Error", f"File not found:\n{file_path}")

    def start_scan(self):
        if self.is_scanning:
            return

        if not config.is_configured():
            messagebox.showwarning(
                "Setup Required",
                "Please set your screenshots folder first.\n\nClick Settings to configure."
            )
            return

        self.is_scanning = True
        self.scan_btn.configure(state=tk.DISABLED)
        self.progress_bar.pack(side=tk.LEFT, padx=(10, 0))
        self.progress_var.set(0)

        # Run scan in background thread
        thread = threading.Thread(target=self.run_scan, daemon=True)
        thread.start()

    def run_scan(self):
        def progress_callback(current, total, filename):
            progress = (current / total) * 100
            self.root.after(0, lambda: self.progress_var.set(progress))
            self.root.after(0, lambda: self.status_var.set(f"Scanning: {filename} ({current}/{total})"))

        try:
            stats = scanner.scan_and_index(progress_callback=progress_callback)
            self.root.after(0, lambda: self.scan_complete(stats))
        except Exception as e:
            self.root.after(0, lambda: self.scan_error(str(e)))

    def scan_complete(self, stats):
        self.is_scanning = False
        self.scan_btn.configure(state=tk.NORMAL)
        self.progress_bar.pack_forget()

        message = (
            f"Scan complete!\n\n"
            f"New: {stats['indexed']}\n"
            f"Skipped (already indexed): {stats['skipped']}\n"
            f"No text found: {stats['failed']}"
        )
        messagebox.showinfo("Scan Complete", message)
        self.update_status()
        self.load_folders()

    def scan_error(self, error: str):
        self.is_scanning = False
        self.scan_btn.configure(state=tk.NORMAL)
        self.progress_bar.pack_forget()

        messagebox.showerror("Scan Error", f"An error occurred:\n{error}")
        self.update_status()

    def show_first_run_setup(self):
        """Show setup dialog on first run."""
        messagebox.showinfo(
            "Welcome to Screenshot Search",
            "Please select your screenshots folder.\n\n"
            "This is typically where ShareX or your screenshot tool saves images."
        )
        self.change_screenshots_folder()

    def show_settings(self):
        """Show settings dialog."""
        # Close existing settings window if open
        if self.settings_window and self.settings_window.winfo_exists():
            self.settings_window.destroy()

        colors = THEMES[self.theme]

        self.settings_window = tk.Toplevel(self.root)
        self.settings_window.title("Settings")
        self.settings_window.geometry("500x280")
        self.settings_window.resizable(False, False)
        self.settings_window.transient(self.root)
        self.settings_window.grab_set()
        self.settings_window.configure(bg=colors["bg"])

        settings_window = self.settings_window  # Local reference for nested functions

        # Screenshots folder setting
        folder_frame = ttk.LabelFrame(settings_window, text="Screenshots Folder", padding="10")
        folder_frame.pack(fill=tk.X, padx=10, pady=10)

        current_folder = config.get_screenshots_folder() or "(Not set)"
        folder_path_var = tk.StringVar(value=current_folder)

        folder_entry = ttk.Entry(folder_frame, textvariable=folder_path_var, width=50, state='readonly')
        folder_entry.pack(side=tk.LEFT, padx=(0, 10))

        def browse_and_update():
            folder = filedialog.askdirectory(
                title="Select Screenshots Folder",
                initialdir=config.get_screenshots_folder() or Path.home()
            )
            if folder:
                config.set_screenshots_folder(folder)
                folder_path_var.set(folder)
                self.update_status()
                self.load_folders()

        browse_btn = ttk.Button(folder_frame, text="Browse...", command=browse_and_update)
        browse_btn.pack(side=tk.LEFT)

        # Layout setting
        layout_frame = ttk.LabelFrame(settings_window, text="Layout", padding="10")
        layout_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

        layout_var = tk.StringVar(value=self.layout)

        def on_layout_change():
            new_layout = layout_var.get()
            if new_layout != self.layout:
                self.switch_layout(new_layout)

        ttk.Radiobutton(
            layout_frame,
            text="Popup preview (click opens a popup with details)",
            variable=layout_var,
            value="popup",
            command=on_layout_change
        ).pack(anchor=tk.W)

        ttk.Radiobutton(
            layout_frame,
            text="Side panel preview (details shown in side panel)",
            variable=layout_var,
            value="side_panel",
            command=on_layout_change
        ).pack(anchor=tk.W)

        # Theme setting
        theme_frame = ttk.LabelFrame(settings_window, text="Theme", padding="10")
        theme_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

        theme_var = tk.StringVar(value=self.theme)

        def on_theme_change():
            new_theme = theme_var.get()
            if new_theme != self.theme:
                self.switch_theme(new_theme)

        ttk.Radiobutton(
            theme_frame,
            text="Light",
            variable=theme_var,
            value="light",
            command=on_theme_change
        ).pack(side=tk.LEFT, padx=(0, 20))

        ttk.Radiobutton(
            theme_frame,
            text="Dark",
            variable=theme_var,
            value="dark",
            command=on_theme_change
        ).pack(side=tk.LEFT)

        # Buttons
        btn_frame = ttk.Frame(settings_window)
        btn_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Button(btn_frame, text="Close", command=settings_window.destroy).pack(side=tk.RIGHT)

    def browse_folder(self, parent_window=None):
        """Open folder browser and save selection."""
        folder = filedialog.askdirectory(
            title="Select Screenshots Folder",
            initialdir=config.get_screenshots_folder() or Path.home()
        )

        if folder:
            config.set_screenshots_folder(folder)
            if hasattr(self, 'folder_path_var'):
                self.folder_path_var.set(folder)
            self.update_status()
            self.load_folders()
            messagebox.showinfo("Settings", f"Screenshots folder set to:\n{folder}")

    def change_screenshots_folder(self):
        """Change the screenshots folder (used for first-run setup)."""
        self.browse_folder()


def main():
    root = tk.Tk()
    app = ScreenshotSearchApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
