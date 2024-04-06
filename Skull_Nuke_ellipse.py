import tkinter as tk

from pynput import keyboard, mouse

# Blast Radius Dictionary (Currently unused)
blast_radius = {
    9: (410, 250),
}  # blast_radius: (width, height)


# Parameters for the ellipse
ELLIPSE_WIDTH = 410
ELLIPSE_HEIGHT = 210
ELLIPSE_COLOR = "#FF0000"  # Red color in hex
TRANSPARENCY = 0.3  # Transparency level


class TransparentEllipse:
    def __init__(self):
        self.root = tk.Tk()
        self.root.attributes("-transparentcolor", "white")
        self.root.attributes("-topmost", True)
        self.root.overrideredirect(True)
        self.canvas = tk.Canvas(
            self.root,
            width=ELLIPSE_WIDTH,
            height=ELLIPSE_HEIGHT,
            bg="white",
            highlightthickness=0,
        )
        self.canvas.pack()
        self.ellipse = self.canvas.create_oval(
            0,
            0,
            ELLIPSE_WIDTH,
            ELLIPSE_HEIGHT,
            fill=ELLIPSE_COLOR,
            outline=ELLIPSE_COLOR,
        )
        self.canvas.itemconfig(
            self.ellipse, stipple="gray50"
        )  # Adding some pattern to simulate transparency
        self.root.attributes("-alpha", TRANSPARENCY)  # Set window transparency

        self.mouse_listener = mouse.Listener(on_move=self.on_move)
        self.mouse_listener.start()

        self.keyboard_listener = keyboard.Listener(
            on_press=self.on_press, on_release=self.on_release
        )
        self.keyboard_listener.start()

        self.root.withdraw()  # Initially hide the window

    def on_move(self, x, y):
        self.root.geometry(f"+{x-ELLIPSE_WIDTH//2}+{y-ELLIPSE_HEIGHT//2}")

    def on_press(self, key):
        try:
            if (
                key == keyboard.Key.ctrl_l or key == keyboard.Key.ctrl_r
            ):  # Check if the key is Ctrl
                self.root.deiconify()  # Show the window
        except AttributeError:
            pass

    def on_release(self, key):
        try:
            if (
                key == keyboard.Key.ctrl_l or key == keyboard.Key.ctrl_r
            ):  # Check if the key is Ctrl
                self.root.withdraw()  # Hide the window
        except AttributeError:
            pass

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    app = TransparentEllipse()
    app.run()
