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
PREVIEW_SIZE = (400, 400)
COLUMNS = 3
MAX_SNIPPET_LENGTH = 60


class ScreenshotSearchApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Screenshot Search")
        self.root.geometry("1100x700")
        self.root.minsize(800, 500)

        # Store image references to prevent garbage collection
        self.thumbnail_refs = []
        self.preview_image_ref = None

        # Currently selected result
        self.selected_result = None

        # Scanning state
        self.is_scanning = False

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

        # Main content area - paned window for results and preview
        main_pane = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        main_pane.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

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

        # Clear previous results and preview
        self.clear_results()
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
                # Single click shows preview, double click opens
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
            if col >= COLUMNS:
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
        """Show the selected screenshot in the preview pane."""
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
                image.thumbnail(PREVIEW_SIZE, Image.Resampling.LANCZOS)
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
        """Copy extracted text to clipboard."""
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
        """Open the selected image in default viewer."""
        if self.selected_result:
            self.open_image(self.selected_result['file_path'])

    def open_folder(self):
        """Open the folder containing the selected image."""
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
        self.load_folders()  # Refresh folder list

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
        settings_window = tk.Toplevel(self.root)
        settings_window.title("Settings")
        settings_window.geometry("500x150")
        settings_window.resizable(False, False)
        settings_window.transient(self.root)
        settings_window.grab_set()

        # Screenshots folder setting
        folder_frame = ttk.LabelFrame(settings_window, text="Screenshots Folder", padding="10")
        folder_frame.pack(fill=tk.X, padx=10, pady=10)

        current_folder = config.get_screenshots_folder() or "(Not set)"
        self.folder_path_var = tk.StringVar(value=current_folder)

        folder_entry = ttk.Entry(folder_frame, textvariable=self.folder_path_var, width=50, state='readonly')
        folder_entry.pack(side=tk.LEFT, padx=(0, 10))

        browse_btn = ttk.Button(folder_frame, text="Browse...", command=lambda: self.browse_folder(settings_window))
        browse_btn.pack(side=tk.LEFT)

        # Buttons
        btn_frame = ttk.Frame(settings_window)
        btn_frame.pack(fill=tk.X, padx=10, pady=10)

        close_btn = ttk.Button(btn_frame, text="Close", command=settings_window.destroy)
        close_btn.pack(side=tk.RIGHT)

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
