"""
Preview panel for displaying participant monitor previews.
"""

import tkinter as tk
from tkinter import ttk, Canvas
from typing import Optional
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

from config.trial import Trial


class MonitorPreview(ttk.LabelFrame):
    """
    Preview widget showing what a participant will see.
    """

    def __init__(self, parent, participant_num: int):
        """
        Initialize monitor preview.

        Args:
            parent: Parent widget
            participant_num: Participant number (1 or 2)
        """
        super().__init__(
            parent,
            text=f"Participant {participant_num} Monitor Preview",
            padding=10
        )

        self.participant_num = participant_num
        self.current_trial: Optional[Trial] = None

        # Preview canvas (16:9 aspect ratio)
        self.canvas = Canvas(self, bg="#000000", width=320, height=180)
        self.canvas.pack(fill=tk.BOTH, expand=True)

        # Info label
        self.info_label = ttk.Label(
            self,
            text="No trial selected",
            font=("Arial", 9, "italic"),
            anchor=tk.CENTER
        )
        self.info_label.pack(fill=tk.X, pady=5)

        # Screen capture state
        self.camera = None
        self.capturing = False
        self.photo = None  # Keep reference to prevent garbage collection

        self._draw_placeholder()

    def _draw_placeholder(self):
        """Draw placeholder content."""
        self.canvas.delete("all")

        # Draw placeholder text
        self.canvas.create_text(
            160, 90,
            text=f"Participant {self.participant_num}\nMonitor Preview",
            fill="#FFFFFF",
            font=("Arial", 12),
            justify=tk.CENTER
        )

    def load_trial(self, trial: Trial):
        """
        Load a trial for preview.

        Args:
            trial: Trial object to preview
        """
        self.current_trial = trial
        self.canvas.delete("all")

        # Get video path for this participant
        video_path = trial.video_path_1 if self.participant_num == 1 else trial.video_path_2

        if video_path:
            # Show video path
            filename = Path(video_path).name
            self.canvas.create_text(
                160, 90,
                text=f"Video: {filename}",
                fill="#FFFFFF",
                font=("Arial", 10),
                justify=tk.CENTER
            )

            self.info_label.config(text=f"Trial {trial.index + 1}: {filename}")
        else:
            self.canvas.create_text(
                160, 90,
                text="No video selected",
                fill="#888888",
                font=("Arial", 10, "italic")
            )

            self.info_label.config(text=f"Trial {trial.index + 1}: No video")

    def clear(self):
        """Clear the preview."""
        self.current_trial = None
        self._draw_placeholder()
        self.info_label.config(text="No trial selected")

    def start_preview(self, screen_index: int):
        """
        Start live screen capture preview.

        Args:
            screen_index: Monitor index for dxcam (0-based)
        """
        try:
            import dxcam
            from PIL import Image, ImageTk

            # Create camera for specified screen
            self.camera = dxcam.create(output_idx=screen_index)
            if self.camera is None:
                raise RuntimeError(f"Failed to create camera for screen {screen_index}")

            self.capturing = True
            self.info_label.config(text=f"Live Preview (Screen {screen_index})")

            # Start capture loop
            self._capture_loop()

        except ImportError:
            self.info_label.config(text="dxcam not installed (Windows only)")
            self._draw_placeholder()
        except Exception as e:
            self.info_label.config(text=f"Preview error: {str(e)}")
            self._draw_placeholder()

    def _capture_loop(self):
        """
        Capture and display frame (scheduled via after()).
        Runs at ~30 fps (33ms intervals).
        """
        if not self.capturing:
            return

        try:
            from PIL import Image, ImageTk

            # Capture current frame from screen
            frame = self.camera.grab()

            if frame is not None:
                # Convert numpy array to PIL Image
                img = Image.fromarray(frame)

                # Get actual canvas dimensions (not the initial 320x180)
                canvas_width = self.canvas.winfo_width()
                canvas_height = self.canvas.winfo_height()

                # Handle case where canvas hasn't been rendered yet
                if canvas_width <= 1 or canvas_height <= 1:
                    canvas_width = 320
                    canvas_height = 180

                # Calculate aspect ratios
                img_aspect = img.width / img.height
                canvas_aspect = canvas_width / canvas_height

                # Debug output (first frame only)
                if not hasattr(self, '_logged_dimensions'):
                    self._logged_dimensions = True
                    print(f"\n[P{self.participant_num} Preview Debug]")
                    print(f"  Captured: {img.width}x{img.height} (aspect: {img_aspect:.3f})")
                    print(f"  Canvas (actual): {canvas_width}x{canvas_height} (aspect: {canvas_aspect:.3f})")

                # Calculate resize dimensions preserving aspect ratio
                if img_aspect > canvas_aspect:
                    # Image is wider - fit to width, add letterboxing top/bottom
                    new_width = canvas_width
                    new_height = int(canvas_width / img_aspect)
                else:
                    # Image is taller - fit to height, add pillarboxing left/right
                    new_height = canvas_height
                    new_width = int(canvas_height * img_aspect)

                # Continue debug output
                if hasattr(self, '_logged_dimensions') and not hasattr(self, '_logged_scale'):
                    self._logged_scale = True
                    print(f"  Scaled to: {new_width}x{new_height}")
                    x_off = (canvas_width - new_width) // 2
                    y_off = (canvas_height - new_height) // 2
                    print(f"  Offsets: x={x_off}, y={y_off}")
                    print(f"  Image center: ({canvas_width // 2}, {canvas_height // 2})")
                    print(f"  Letterboxing: {'Top/Bottom' if img_aspect > canvas_aspect else 'Left/Right'}")

                # Resize image preserving aspect ratio
                img_resized = img.resize((new_width, new_height), Image.LANCZOS)

                # Create black canvas background
                canvas_img = Image.new('RGB', (canvas_width, canvas_height), color='black')

                # Calculate position to center the image
                x_offset = (canvas_width - new_width) // 2
                y_offset = (canvas_height - new_height) // 2

                # Paste resized image centered on black background
                canvas_img.paste(img_resized, (x_offset, y_offset))

                # Convert to PhotoImage for Tkinter
                self.photo = ImageTk.PhotoImage(canvas_img)

                # Update canvas - center the image at actual canvas center
                self.canvas.delete("all")
                center_x = canvas_width // 2
                center_y = canvas_height // 2
                self.canvas.create_image(center_x, center_y, anchor=tk.CENTER, image=self.photo)

        except Exception as e:
            # Log error but continue trying
            print(f"Capture error for P{self.participant_num}: {e}")

        # Schedule next capture (30 fps = ~33ms)
        if self.capturing:
            self.after(33, self._capture_loop)

    def stop_preview(self):
        """
        Stop live preview and cleanup resources.
        """
        self.capturing = False

        if self.camera:
            try:
                self.camera.release()
            except Exception as e:
                print(f"Error releasing camera: {e}")
            finally:
                self.camera = None

        # Clear photo reference
        self.photo = None

        # Show placeholder
        self._draw_placeholder()
        self.info_label.config(text="Preview stopped")


class PreviewPanel(ttk.Frame):
    """
    Panel containing previews for both participant monitors.
    """

    def __init__(self, parent):
        """
        Initialize preview panel with dual monitor previews.

        Args:
            parent: Parent widget
        """
        super().__init__(parent)

        # Title
        title_label = ttk.Label(
            self,
            text="Monitor Previews",
            font=("Arial", 12, "bold")
        )
        title_label.pack(pady=5)

        # Container for both previews
        preview_container = ttk.Frame(self)
        preview_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # Participant 1 preview
        self.preview1 = MonitorPreview(preview_container, participant_num=1)
        self.preview1.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)

        # Participant 2 preview
        self.preview2 = MonitorPreview(preview_container, participant_num=2)
        self.preview2.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)

    def load_trial(self, trial: Trial):
        """
        Load a trial for preview on both monitors.

        Args:
            trial: Trial object to preview
        """
        self.preview1.load_trial(trial)
        self.preview2.load_trial(trial)

    def clear(self):
        """Clear both previews."""
        self.preview1.clear()
        self.preview2.clear()

    def start_live_previews(self, screen_index_p1: int, screen_index_p2: int):
        """
        Start live screen capture for both participant monitors.

        Args:
            screen_index_p1: Monitor index for participant 1 (dxcam 0-based)
            screen_index_p2: Monitor index for participant 2 (dxcam 0-based)
        """
        self.preview1.start_preview(screen_index_p1)
        self.preview2.start_preview(screen_index_p2)

    def stop_live_previews(self):
        """
        Stop live screen capture for both participant monitors.
        """
        self.preview1.stop_preview()
        self.preview2.stop_preview()
