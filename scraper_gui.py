"""JanitorAI Scraper GUI - Modern user interface matching screenshot design"""

import logging
import threading
import webbrowser
from datetime import datetime, timedelta
from tkinter import *
from tkinter import ttk, messagebox, filedialog
from typing import Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ModernScraperGUI:
    """Modern GUI application for JanitorAI Scraper"""
    
    # Color scheme - Matching the screenshots exactly
    COLORS = {
        'primary': '#6366f1',      # Blue-purple (Discord button)
        'primary_hover': '#5558e3',
        'danger': '#ef4444',       # Red (Stop button)
        'danger_hover': '#dc2626',
        'success': '#10b981',      # Green
        'warning': '#f59e0b',      # Orange/Amber
        
        # Backgrounds
        'bg_app': '#0f172a',       # Deep navy (app background)
        'bg_card': '#1e293b',      # Card background
        'bg_input': '#334155',     # Input fields
        'bg_darker': '#0a0f1e',    # Even darker for log
        
        # Text
        'text_main': '#f1f5f9',    # Almost white
        'text_sub': '#94a3b8',     # Gray for descriptions
        'text_muted': '#64748b',   # More muted gray
        
        # Borders & accents
        'border': '#334155',
        'accent': '#6366f1',
    }
    
    OPT_OUT_URL = "https://forms.gle/3Ji6o1E159JZpatu9"
    DISCORD_URL = "https://discord.gg/Y6TndrAYmz"
    
    def __init__(self):
        self.root = Tk()
        self.root.title("JanitorAI Scraper")
        self.root.geometry("1100x900")
        self.root.configure(bg=self.COLORS['bg_app'])
        
        # Set icon if exists
        try:
            from pathlib import Path
            if Path("icon.ico").exists():
                self.root.iconbitmap("icon.ico")
        except Exception:
            pass
        
        # Apply modern theme
        self._setup_styles()
        
        # State variables
        self.scraper_thread: Optional[threading.Thread] = None
        self.stop_requested = False
        self.start_time: Optional[datetime] = None
        self.processed_count = 0
        self.total_count = 0
        self.config_vars = {}
        
        # Scraper instance (persistent across start/stop)
        self.scraper = None
        self.browser_ready = False
        
        # Build UI
        self._create_ui()
        
        # Center window
        self._center_window()
        
        # Launch browser automatically on startup
        self.root.after(500, self._launch_browser_on_startup)
    
    def _setup_styles(self):
        """Setup modern ttk styles"""
        style = ttk.Style()
        style.theme_use('clam')
        
        # Configure base styles
        style.configure('.', background=self.COLORS['bg_app'], 
                       foreground=self.COLORS['text_main'])
        
        # Frames
        style.configure('TFrame', background=self.COLORS['bg_app'])
        style.configure('Card.TFrame', background=self.COLORS['bg_card'])
        
        # Labels
        style.configure('TLabel', background=self.COLORS['bg_app'], 
                       foreground=self.COLORS['text_main'])
        style.configure('Card.TLabel', background=self.COLORS['bg_card'], 
                       foreground=self.COLORS['text_main'])
        
        # Entry
        style.configure('TEntry', fieldbackground=self.COLORS['bg_input'], 
                       foreground=self.COLORS['text_main'], borderwidth=0, 
                       relief='flat')
        
        # Spinbox
        style.configure('TSpinbox', fieldbackground=self.COLORS['bg_input'],
                       foreground=self.COLORS['text_main'], 
                       arrowcolor=self.COLORS['text_main'], borderwidth=0)
        
        # Checkbutton
        style.configure('TCheckbutton', background=self.COLORS['bg_card'],
                       foreground=self.COLORS['text_main'])
        
        # Progressbar
        style.configure('TProgressbar', troughcolor=self.COLORS['bg_input'],
                       background=self.COLORS['primary'], thickness=8, 
                       borderwidth=0)
        
        # Separator
        style.configure('TSeparator', background=self.COLORS['border'])
        
        # Scrollbar
        style.configure('Vertical.TScrollbar', 
                       background=self.COLORS['bg_input'],
                       troughcolor=self.COLORS['bg_app'],
                       borderwidth=0,
                       arrowcolor=self.COLORS['text_main'])
    
    def _center_window(self):
        """Center the window on screen"""
        self.root.update_idletasks()
        x = (self.root.winfo_screenwidth() - self.root.winfo_width()) // 2
        y = (self.root.winfo_screenheight() - self.root.winfo_height()) // 2
        self.root.geometry(f"+{x}+{y}")
    
    def _create_ui(self):
        """Create the main UI"""
        # Create canvas with scrollbar
        canvas = Canvas(self.root, bg=self.COLORS['bg_app'], 
                       highlightthickness=0)
        scrollbar = ttk.Scrollbar(self.root, orient=VERTICAL, 
                                 command=canvas.yview)
        
        # Scrollable frame
        scrollable_frame = Frame(canvas, bg=self.COLORS['bg_app'])
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw", 
                           width=1060)
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Main container with padding
        main_frame = Frame(scrollable_frame, bg=self.COLORS['bg_app'])
        main_frame.pack(fill=BOTH, expand=True, padx=40, pady=30)
        
        # Header with icon
        self._create_header(main_frame)
        
        # Quick Links
        self._create_links(main_frame)
        
        # Configuration Card
        self._create_config_card(main_frame)
        
        # Progress Card
        self._create_progress_card(main_frame)
        
        # Log Card
        self._create_log_card(main_frame)
        
        # Control Buttons
        self._create_control_buttons(main_frame)
        
        # Pack canvas and scrollbar
        canvas.pack(side=LEFT, fill=BOTH, expand=True)
        scrollbar.pack(side=RIGHT, fill=Y)
        
        # Bind mousewheel
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)
    
    def _create_header(self, parent):
        """Create header with icon and title"""
        header_frame = Frame(parent, bg=self.COLORS['bg_app'])
        header_frame.pack(fill=X, pady=(0, 25))
        
        # Create a card-like container for the header
        header_card = Frame(header_frame, bg=self.COLORS['bg_card'], 
                           highlightbackground=self.COLORS['accent'],
                           highlightthickness=2)
        header_card.pack(fill=X, pady=10)
        
        # Content inside header card
        content = Frame(header_card, bg=self.COLORS['bg_card'])
        content.pack(pady=25, padx=30)
        
        # Icon + Title row
        title_row = Frame(content, bg=self.COLORS['bg_card'])
        title_row.pack()
        
        # Icon (robot emoji)
        icon = Label(title_row, text="🤖", font=('Segoe UI', 36),
                    bg=self.COLORS['bg_card'])
        icon.pack(side=LEFT, padx=(0, 15))
        
        # Title text
        title_text = Frame(title_row, bg=self.COLORS['bg_card'])
        title_text.pack(side=LEFT)
        
        title = Label(title_text, text="JanitorAI Scraper",
                     font=('Segoe UI', 32, 'bold'),
                     fg=self.COLORS['text_main'],
                     bg=self.COLORS['bg_card'])
        title.pack(anchor=W)
        
        subtitle = Label(title_text, 
                        text="Export your characters and chat histories with ease",
                        font=('Segoe UI', 11),
                        fg=self.COLORS['text_sub'],
                        bg=self.COLORS['bg_card'])
        subtitle.pack(anchor=W)
    
    def _create_links(self, parent):
        """Create links section"""
        links_frame = Frame(parent, bg=self.COLORS['bg_app'])
        links_frame.pack(fill=X, pady=(0, 20))
        
        # Opt-out button
        opt_btn = Button(links_frame, text="🚫 Creator Opt-Out",
                        command=lambda: webbrowser.open(self.OPT_OUT_URL),
                        bg=self.COLORS['bg_card'], fg=self.COLORS['text_main'],
                        font=('Segoe UI', 10), padx=20, pady=10,
                        relief='flat', cursor='hand2', borderwidth=0,
                        activebackground=self.COLORS['bg_input'],
                        activeforeground=self.COLORS['text_main'])
        opt_btn.pack(side=LEFT, padx=(0, 10))
        
        # Discord button
        discord_btn = Button(links_frame, text="💬 Discord Support",
                            command=lambda: webbrowser.open(self.DISCORD_URL),
                            bg=self.COLORS['primary'], 
                            fg='white',
                            font=('Segoe UI', 10, 'bold'), 
                            padx=20, pady=10,
                            relief='flat', cursor='hand2', borderwidth=0,
                            activebackground=self.COLORS['primary_hover'],
                            activeforeground='white')
        discord_btn.pack(side=LEFT)
    
    def _create_config_card(self, parent):
        """Create configuration card"""
        card = self._create_card(parent, "⚙️ Configuration")
        
        # Output folder
        self._create_setting_row(card, "Output Folder",
                                 "Choose where to save exported files",
                                 self._create_folder_selector)
        
        self._add_spacing(card, 10)
        
        # Minimum messages
        self._create_setting_row(card, "Minimum Messages",
                                 "Chats must have at least this many messages to be saved",
                                 lambda p: self._create_number_input(p, "message_limit", 
                                                                     1, 100, 4))
        
        self._add_spacing(card, 10)
        
        # Request speed
        self._create_setting_row(card, "Request Speed",
                                 "Delay between requests (seconds) - lower is faster but riskier",
                                 lambda p: self._create_number_input(p, "delay", 
                                                                     0.5, 10.0, 2.0, 0.5))
        
        # Separator
        ttk.Separator(card, orient=HORIZONTAL).pack(fill=X, pady=20)
        
        # Export Options header
        options_label = Label(card, text="📦 Export Options",
                             font=('Segoe UI', 11, 'bold'),
                             fg=self.COLORS['text_main'],
                             bg=self.COLORS['bg_card'])
        options_label.pack(anchor=W, pady=(0, 10))
        
        # Checkboxes
        self._create_checkbox(card, "keep_partial", "📝 Keep partial chats",
                             "Save chats even if they have fewer messages than the minimum",
                             False)
        
        self._create_checkbox(card, "keep_json", "💾 Save JSON files",
                             "Export additional JSON files alongside PNG character cards",
                             False)
        
        self._create_checkbox(card, "extract_personas", "👤 Export personas",
                             "Include your user personas and generation settings",
                             True)
        
        self._create_checkbox(card, "organize_st", "📁 SillyTavern format",
                             "Organize exported files for easy import into SillyTavern",
                             True)
        
        self._create_checkbox(card, "recover_deleted", "🔄 Recover deleted/private chats",
                             "⚠️ Only recovers chat histories, not character cards",
                             True, warning=True)
    
    def _create_progress_card(self, parent):
        """Create progress card"""
        card = self._create_card(parent, "📊 Progress")
        
        # Status text
        self.current_label = Label(card, text="⏸️ Ready to start",
                                  font=('Segoe UI', 10),
                                  fg=self.COLORS['text_sub'],
                                  bg=self.COLORS['bg_card'])
        self.current_label.pack(anchor=W, pady=(0, 12))
        
        # Progress bar
        self.progress_var = DoubleVar(value=0)
        self.progress_bar = ttk.Progressbar(card, variable=self.progress_var,
                                           maximum=100, mode="determinate")
        self.progress_bar.pack(fill=X, pady=(0, 15))
        
        # Stats container
        stats_frame = Frame(card, bg=self.COLORS['bg_card'])
        stats_frame.pack(fill=X)
        
        # Left stats
        left_stats = Frame(stats_frame, bg=self.COLORS['bg_card'])
        left_stats.pack(side=LEFT)
        
        self.stats_label = Label(left_stats, text="0 / 0 characters",
                                font=('Segoe UI', 11, 'bold'),
                                fg=self.COLORS['text_main'],
                                bg=self.COLORS['bg_card'])
        self.stats_label.pack(anchor=W)
        
        self.chats_label = Label(left_stats, text="0 chats saved",
                                font=('Segoe UI', 9),
                                fg=self.COLORS['success'],
                                bg=self.COLORS['bg_card'])
        self.chats_label.pack(anchor=W)
        
        # Right stats (ETA)
        self.eta_label = Label(stats_frame, text="🕐 ETA: --:--",
                              font=('Segoe UI', 10),
                              fg=self.COLORS['text_sub'],
                              bg=self.COLORS['bg_card'])
        self.eta_label.pack(side=RIGHT)
    
    def _create_log_card(self, parent):
        """Create log card"""
        card = self._create_card(parent, "📋 Activity Log")
        
        # Log text
        self.log_text = Text(card, height=10, wrap=WORD,
                            bg=self.COLORS['bg_darker'],
                            fg=self.COLORS['text_main'],
                            font=('Consolas', 9),
                            relief='flat', padx=15, pady=12,
                            state=DISABLED, borderwidth=0,
                            insertbackground=self.COLORS['text_main'])
        
        scrollbar = Scrollbar(card, command=self.log_text.yview,
                            bg=self.COLORS['bg_input'],
                            troughcolor=self.COLORS['bg_darker'],
                            activebackground=self.COLORS['border'])
        self.log_text.configure(yscrollcommand=scrollbar.set)
        
        self.log_text.pack(side=LEFT, fill=BOTH, expand=True)
        scrollbar.pack(side=RIGHT, fill=Y)
        
        # Placeholder text
        self.log_text.configure(state=NORMAL)
        self.log_text.insert(END, "Logs will appear here...", "placeholder")
        self.log_text.tag_config("placeholder", foreground=self.COLORS['text_muted'])
        self.log_text.configure(state=DISABLED)
    
    def _create_control_buttons(self, parent):
        """Create control buttons"""
        button_frame = Frame(parent, bg=self.COLORS['bg_app'])
        button_frame.pack(fill=X, pady=(25, 0))
        
        # Start button
        self.start_btn = Button(button_frame, text="▶ Start Scraping",
                               command=self._start_scraper,
                               bg=self.COLORS['primary'], fg='white',
                               font=('Segoe UI', 12, 'bold'),
                               padx=40, pady=14, relief='flat',
                               cursor='hand2', borderwidth=0,
                               activebackground=self.COLORS['primary_hover'],
                               activeforeground='white')
        self.start_btn.pack(side=LEFT, padx=(0, 12))
        
        # Stop button
        self.stop_btn = Button(button_frame, text="⏹ Stop",
                              command=self._stop_scraper,
                              bg=self.COLORS['danger'], fg='white',
                              font=('Segoe UI', 12, 'bold'),
                              padx=30, pady=14, relief='flat',
                              cursor='hand2', state=DISABLED, borderwidth=0,
                              activebackground=self.COLORS['danger_hover'],
                              activeforeground='white',
                              disabledforeground='#475569')
        self.stop_btn.pack(side=LEFT)
        
        # Style disabled state
        self.stop_btn.configure(bg='#334155')
    
    def _create_card(self, parent, title):
        """Create a card container"""
        # Card frame with border
        card_frame = Frame(parent, bg=self.COLORS['bg_card'],
                          highlightbackground=self.COLORS['border'],
                          highlightthickness=1)
        card_frame.pack(fill=BOTH, expand=True, pady=(0, 20))
        
        # Title
        title_label = Label(card_frame, text=title,
                           font=('Segoe UI', 13, 'bold'),
                           fg=self.COLORS['text_main'],
                           bg=self.COLORS['bg_card'])
        title_label.pack(anchor=W, padx=25, pady=(20, 15))
        
        # Content container
        content = Frame(card_frame, bg=self.COLORS['bg_card'])
        content.pack(fill=BOTH, expand=True, padx=25, pady=(0, 20))
        
        return content
    
    def _create_setting_row(self, parent, label, description, widget_creator):
        """Create a setting row"""
        row = Frame(parent, bg=self.COLORS['bg_card'])
        row.pack(fill=X, pady=5)
        
        # Left side - labels
        label_frame = Frame(row, bg=self.COLORS['bg_card'])
        label_frame.pack(side=LEFT, fill=X, expand=True)
        
        lbl = Label(label_frame, text=label,
                   font=('Segoe UI', 10, 'bold'),
                   fg=self.COLORS['text_main'],
                   bg=self.COLORS['bg_card'])
        lbl.pack(anchor=W)
        
        desc = Label(label_frame, text=description,
                    font=('Segoe UI', 9),
                    fg=self.COLORS['text_sub'],
                    bg=self.COLORS['bg_card'])
        desc.pack(anchor=W)
        
        # Right side - widget
        widget_creator(row)
    
    def _create_folder_selector(self, parent):
        """Create folder selector"""
        widget_frame = Frame(parent, bg=self.COLORS['bg_card'])
        widget_frame.pack(side=RIGHT)
        
        self.config_vars["output_dir"] = StringVar(value="Output")
        
        entry = Entry(widget_frame, 
                     textvariable=self.config_vars["output_dir"],
                     width=20, font=('Segoe UI', 10),
                     bg=self.COLORS['bg_input'],
                     fg=self.COLORS['text_main'],
                     relief='flat', borderwidth=0,
                     insertbackground=self.COLORS['text_main'])
        entry.pack(side=LEFT, padx=(0, 8), ipady=6, ipadx=8)
        
        btn = Button(widget_frame, text="📁 Browse",
                    command=self._browse_output,
                    bg=self.COLORS['bg_input'],
                    fg=self.COLORS['text_main'],
                    font=('Segoe UI', 9),
                    padx=12, pady=6, relief='flat',
                    cursor='hand2', borderwidth=0,
                    activebackground=self.COLORS['border'],
                    activeforeground=self.COLORS['text_main'])
        btn.pack(side=LEFT)
    
    def _create_number_input(self, parent, var_name, min_val, max_val,
                            default_val, increment=1):
        """Create number input"""
        widget_frame = Frame(parent, bg=self.COLORS['bg_card'])
        widget_frame.pack(side=RIGHT)
        
        if isinstance(increment, float):
            self.config_vars[var_name] = DoubleVar(value=default_val)
        else:
            self.config_vars[var_name] = IntVar(value=default_val)
        
        spinbox = Spinbox(widget_frame, from_=min_val, to=max_val,
                         increment=increment,
                         textvariable=self.config_vars[var_name],
                         width=12, font=('Segoe UI', 10),
                         bg=self.COLORS['bg_input'],
                         fg=self.COLORS['text_main'],
                         buttonbackground=self.COLORS['bg_input'],
                         relief='flat', borderwidth=0,
                         insertbackground=self.COLORS['text_main'])
        spinbox.pack(ipady=4, ipadx=4)
    
    def _create_checkbox(self, parent, var_name, label, description, 
                        default, warning=False):
        """Create checkbox with description"""
        frame = Frame(parent, bg=self.COLORS['bg_card'])
        frame.pack(fill=X, pady=6)
        
        self.config_vars[var_name] = BooleanVar(value=default)
        
        # Checkbox
        cb_frame = Frame(frame, bg=self.COLORS['bg_card'])
        cb_frame.pack(anchor=W)
        
        cb = Checkbutton(cb_frame, text=label,
                        variable=self.config_vars[var_name],
                        font=('Segoe UI', 10),
                        bg=self.COLORS['bg_card'],
                        fg=self.COLORS['text_main'],
                        selectcolor=self.COLORS['bg_input'],
                        activebackground=self.COLORS['bg_card'],
                        activeforeground=self.COLORS['text_main'],
                        relief='flat', borderwidth=0)
        cb.pack(side=LEFT)
        
        # Description (with warning styling if needed)
        desc_color = self.COLORS['warning'] if warning else self.COLORS['text_sub']
        desc_text = f"   {description}"
        
        desc = Label(frame, text=desc_text,
                    font=('Segoe UI', 9),
                    fg=desc_color,
                    bg=self.COLORS['bg_card'])
        desc.pack(anchor=W, padx=(25, 0))
    
    def _add_spacing(self, parent, height):
        """Add vertical spacing"""
        Frame(parent, height=height, bg=self.COLORS['bg_card']).pack()
    
    def _browse_output(self):
        """Browse for output directory"""
        folder = filedialog.askdirectory(
            initialdir=self.config_vars["output_dir"].get()
        )
        if folder:
            self.config_vars["output_dir"].set(folder)
    
    def _log(self, message: str, clear_placeholder=False):
        """Add message to log"""
        self.log_text.configure(state=NORMAL)
        
        # Clear placeholder on first real log
        if clear_placeholder or "Logs will appear here" in self.log_text.get(1.0, END):
            self.log_text.delete(1.0, END)
        
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        # Color based on message type
        if "error" in message.lower() or "failed" in message.lower():
            color = self.COLORS['danger']
        elif "success" in message.lower() or "completed" in message.lower():
            color = self.COLORS['success']
        elif "warning" in message.lower():
            color = self.COLORS['warning']
        else:
            color = self.COLORS['text_main']
        
        self.log_text.insert(END, f"[{timestamp}] ", "timestamp")
        self.log_text.insert(END, f"{message}\n", "message")
        
        self.log_text.tag_config("timestamp", foreground=self.COLORS['text_muted'])
        self.log_text.tag_config("message", foreground=color)
        
        self.log_text.see(END)
        self.log_text.configure(state=DISABLED)
    
    def _update_progress(self, current: int, total: int, 
                        current_name: str = "", chats_saved: int = 0):
        """Update progress display"""
        self.processed_count = current
        self.total_count = total
        
        if total > 0:
            percent = (current / total) * 100
            self.progress_var.set(percent)
        
        status_text = f"Processing: {current_name}" if current_name else "Processing..."
        self.current_label.config(text=status_text)
        self.stats_label.config(text=f"{current} / {total} characters")
        self.chats_label.config(text=f"{chats_saved} chats saved")
        
        if self.start_time and current > 0:
            elapsed = (datetime.now() - self.start_time).total_seconds()
            avg_time = elapsed / current
            remaining = (total - current) * avg_time
            eta = timedelta(seconds=int(remaining))
            self.eta_label.config(text=f"🕐 ETA: {str(eta)}")
        
        self.root.update_idletasks()
    
    def _start_scraper(self):
        """Start the scraper"""
        if not self.browser_ready:
            messagebox.showwarning("Not Ready",
                                  "Please wait for browser to launch and log in first!")
            return
        
        if self.scraper_thread and self.scraper_thread.is_alive():
            messagebox.showwarning("Already Running",
                                  "Scraper is already running!")
            return
        
        self.start_btn.config(state=DISABLED, bg='#334155')
        self.stop_btn.config(state=NORMAL, bg=self.COLORS['danger'])
        self.stop_requested = False
        self.start_time = datetime.now()
        
        self._log("🚀 Starting scraper process...")
        
        self.scraper_thread = threading.Thread(target=self._run_scraper, 
                                              daemon=True)
        self.scraper_thread.start()
    
    def _stop_scraper(self):
        """Request scraper to stop"""
        self.stop_requested = True
        self._log("⏸️ Stop requested... waiting for current operation.")
        self.stop_btn.config(state=DISABLED, bg='#334155')
    
    def _launch_browser_on_startup(self):
        """Launch browser when app starts"""
        self._log("🌐 Launching browser...", clear_placeholder=True)
        
        # Run in background thread
        def launch():
            try:
                from scraper_config import ScraperConfig
                from holy_grail_scraper import HolyGrailScraper
                from scraper_utils import setup_logging
                
                setup_logging()
                
                # Create config with defaults (will be updated when Start is clicked)
                config = ScraperConfig(
                    message_limit=4,
                    delay_between_requests=2.0,
                    delay_between_chats=3.0,
                    output_dir="Output",
                )
                
                self.scraper = HolyGrailScraper(config)
                self.scraper.progress_callback = self._on_progress
                self.scraper.log_callback = self._on_log
                self.scraper.stop_check = lambda: self.stop_requested
                
                # Launch browser
                if self.scraper.launch_browser():
                    self._on_log("✅ Browser launched! Please log into JanitorAI.")
                    self._on_log("📝 Once logged in, click 'Start Scraping' to begin.")
                    self.browser_ready = True
                else:
                    self._on_log("❌ Failed to launch browser!")
            
            except Exception as e:
                self._on_log(f"❌ Error launching browser: {e}")
                logger.exception("Browser launch error")
        
        threading.Thread(target=launch, daemon=True).start()
    
    def _run_scraper(self):
        """Run the scraper (background thread)"""
        try:
            # Update config with current GUI values
            self.scraper.config.message_limit = self.config_vars["message_limit"].get()
            self.scraper.config.delay_between_requests = self.config_vars["delay"].get()
            self.scraper.config.delay_between_chats = self.config_vars["delay"].get() + 1.0
            self.scraper.config.output_dir = self.config_vars["output_dir"].get()
            self.scraper.config.keep_partial_extracts = self.config_vars["keep_partial"].get()
            self.scraper.config.keep_character_json = self.config_vars["keep_json"].get()
            self.scraper.config.extract_personas = self.config_vars["extract_personas"].get()
            self.scraper.config.organize_for_sillytavern = self.config_vars["organize_st"].get()
            self.scraper.config.recover_deleted_private_chats = self.config_vars["recover_deleted"].get()
            
            # Update file manager output dir
            self.scraper.file_manager.output_dir = self.scraper.config.output_dir
            
            # Run the scraper
            self.scraper.run()
            self._on_log("✅ Scraper completed successfully!")
            
        except Exception as e:
            self._on_log(f"❌ Error: {e}")
            logger.exception("Scraper error")
        
        finally:
            self.root.after(0, self._on_scraper_finished)
    
    def _on_progress(self, current: int, total: int, name: str = "", 
                    chats: int = 0):
        """Progress callback"""
        self.root.after(0, lambda: self._update_progress(current, total, 
                                                         name, chats))
    
    def _on_log(self, message: str):
        """Log callback"""
        self.root.after(0, lambda: self._log(message))
    
    def _on_scraper_finished(self):
        """Called when scraper finishes"""
        self.start_btn.config(state=NORMAL, bg=self.COLORS['primary'])
        self.stop_btn.config(state=DISABLED, bg='#334155')
        self.current_label.config(text="✅ Finished!")
        messagebox.showinfo("Complete", 
                          "Scraper has finished successfully!")
    
    def run(self):
        """Start the GUI"""
        self.root.mainloop()


def main():
    """Main entry point"""
    app = ModernScraperGUI()
    app.run()


if __name__ == "__main__":
    import multiprocessing
    multiprocessing.freeze_support()
    main()
