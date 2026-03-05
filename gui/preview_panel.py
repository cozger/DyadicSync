"""
Preview panel for displaying participant monitor previews.
"""

import tkinter as tk
from tkinter import ttk, Canvas
from typing import Optional, Dict, Tuple
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

from config.trial import Trial


def _find_dxcam_output(screen_x: int, screen_y: int,
                       screen_width: int, screen_height: int
                       ) -> Optional[Tuple[int, int]]:
    """
    Match Pyglet screen coordinates to dxcam (device_idx, output_idx).

    Pyglet (GDI EnumDisplayMonitors) and dxcam (DXGI EnumOutputs) may enumerate
    monitors in different orders. This function matches by desktop coordinates
    to find the correct dxcam output regardless of enumeration order.

    Args:
        screen_x: Left coordinate of the screen
        screen_y: Top coordinate of the screen
        screen_width: Width of the screen in pixels
        screen_height: Height of the screen in pixels

    Returns:
        Tuple of (device_idx, output_idx) for dxcam.create(), or None if no match
    """
    try:
        import dxcam
        # Access the module-level factory singleton that tracks all DXGI outputs
        factory = dxcam.__dict__['__factory']
        for device_idx, outputs in enumerate(factory.outputs):
            for output_idx, output in enumerate(outputs):
                output.update_desc()
                coords = output.desc.DesktopCoordinates
                if (coords.left == screen_x and coords.top == screen_y and
                        (coords.right - coords.left) == screen_width and
                        (coords.bottom - coords.top) == screen_height):
                    return (device_idx, output_idx)
    except Exception as e:
        print(f"[Preview] Error matching dxcam output by coordinates: {e}")
    return None


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

    def start_preview(self, screen_index: int,
                      screen_info: Optional[Dict[str, int]] = None):
        """
        Start live screen capture preview.

        Args:
            screen_index: Pyglet screen index (used as label and fallback)
            screen_info: Optional dict with {x, y, width, height} from Pyglet/DisplayInfo.
                         When provided, coordinates are used to find the correct dxcam
                         output (since Pyglet and dxcam may enumerate monitors differently).
        """
        try:
            import dxcam
            from PIL import Image, ImageTk

            device_idx = 0
            output_idx = screen_index  # fallback: assume index equality

            # Use coordinate-based mapping if screen_info provided
            if screen_info is not None:
                match = _find_dxcam_output(
                    screen_info['x'], screen_info['y'],
                    screen_info['width'], screen_info['height']
                )
                if match is not None:
                    device_idx, output_idx = match
                    print(f"[Preview] P{self.participant_num}: Pyglet screen {screen_index} "
                          f"-> dxcam device={device_idx}, output={output_idx} "
                          f"(matched at {screen_info['x']},{screen_info['y']} "
                          f"{screen_info['width']}x{screen_info['height']})")
                else:
                    print(f"[Preview] P{self.participant_num}: No dxcam match for coords "
                          f"({screen_info['x']},{screen_info['y']} "
                          f"{screen_info['width']}x{screen_info['height']}), "
                          f"falling back to output_idx={screen_index}")

            # Create camera for the resolved output
            self.camera = dxcam.create(device_idx=device_idx, output_idx=output_idx)
            if self.camera is None:
                raise RuntimeError(
                    f"Failed to create camera (device={device_idx}, output={output_idx})")

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

    def start_live_previews(self, screen_index_p1: int, screen_index_p2: int,
                            screen_info_p1: Optional[Dict[str, int]] = None,
                            screen_info_p2: Optional[Dict[str, int]] = None):
        """
        Start live screen capture for both participant monitors.

        Args:
            screen_index_p1: Pyglet screen index for participant 1
            screen_index_p2: Pyglet screen index for participant 2
            screen_info_p1: Optional {x, y, width, height} for P1 screen
            screen_info_p2: Optional {x, y, width, height} for P2 screen
        """
        self.preview1.start_preview(screen_index_p1, screen_info=screen_info_p1)
        self.preview2.start_preview(screen_index_p2, screen_info=screen_info_p2)

    def stop_live_previews(self):
        """
        Stop live screen capture for both participant monitors.
        """
        self.preview1.stop_preview()
        self.preview2.stop_preview()
