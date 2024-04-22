import asyncio
import ctypes
import json
import os
import threading
from datetime import datetime, timedelta
from pathlib import Path

import customtkinter as ctk
from PIL import Image
from winotify import Notification, audio

ctk.set_appearance_mode("dark")

global main_window  # main_window gets defined if __name__ == "__main__"

MAIN_PATH = os.path.abspath(os.path.dirname(__file__))

MAIN_IMAGES_PATH = Path(MAIN_PATH, "Images")

PLANETS_IMAGES_PATH = Path(MAIN_IMAGES_PATH, "Planets")

LOCK_FILE_PATH = Path(MAIN_PATH, "notification_manager.lock")


# FIXME: Fix an issue where a notification is sent twice (most likely because the old instance is still running)
class NotificationManager:
    def __init__(self):
        self.running = True
        self.next_check_time = None
        self.sleep_event = asyncio.Event()

    async def notification_checker(self) -> None:
        settings = MainWindow.load_settings()
        self.global_settings = settings["global_settings"]
        self.first_iteration = settings["global_settings"][
            "disable_notifications_during_startup"
        ]

        while self.running:
            self.data = MainWindow.load_data()
            min_cooldown_time = None

            # Process each item and task, updating GUI and calculating minimum cooldown time
            for item in ["star_battery", "tool_case", "helmet"]:
                scheduled_time = self.data[item]["cooldown"]
                if MainWindow.compare_to_current_time(scheduled_time):
                    MainWindow.set_item_text(main_window, item)
                    self.cooldown_finished(item=item)
                    self.process_notification(item=item)
                min_cooldown_time = self.update_min_cooldown_time(
                    min_cooldown_time, scheduled_time
                )

            for section in ["workers", "buildings"]:
                for task_id, task_info in self.data[section].items():
                    if not task_info["cooldown_finished"]:
                        scheduled_time = task_info["cooldown"]
                        if MainWindow.compare_to_current_time(scheduled_time):
                            self.cooldown_finished(section=section, task_id=task_id)
                            self.process_notification(
                                section=section, task_info=task_info
                            )
                            if section == "workers":
                                MainWindow.workers_tasks_display(main_window)
                            elif section == "buildings":
                                MainWindow.buildings_tasks_display(main_window)
                        min_cooldown_time = self.update_min_cooldown_time(
                            min_cooldown_time, scheduled_time
                        )

            if self.first_iteration:
                self.first_iteration = False

            # Calculate sleep duration
            if min_cooldown_time:
                sleep_duration = max(
                    min_cooldown_time - datetime.now(), timedelta(seconds=1)
                ).total_seconds()
                sleep_duration = min(sleep_duration, 60)
            else:
                sleep_duration = 60

            # Wait for the sleep duration or until the event is set
            print(f"Sleeping for {sleep_duration} seconds...")
            await asyncio.sleep(sleep_duration)

    def process_notification(
        self,
        *,
        item: str | None = None,
        section: str | None = None,
        task_info: str | None = None,
    ) -> None:
        if (
            section is not None
            and task_info is not None
            and self.global_settings[section]
            and not self.first_iteration
            and not task_info["cooldown_finished"]
        ):
            message = f"Your {task_info['building'] if section == 'buildings' else 'Worker'} on {task_info['planet']} is done!"
            self.send_notification(message)

        if (
            item is not None
            and self.global_settings[item]
            and not self.first_iteration
            and not self.data[item]["cooldown_finished"]
        ):
            message = f"You can collect your {item.replace('_', ' ').title()} again!"
            self.send_notification(message)

    def send_notification(self, message: str) -> None:
        """
        Sends the notification using winotify.

        :param message: The message to be displayed in the notification
        """
        title = "Galaxy Life Notifier"
        icon_path = str(Path(MAIN_IMAGES_PATH, "Starling_Postman_AI_Upscaled.ico"))

        # Create a notification
        toast = Notification(
            app_id="Galaxy Life Notifier",
            title=title,
            msg=message,
            icon=icon_path,
            duration="short",
        )

        # Optionally, you can add sound to the notification
        toast.set_audio(audio.Default, loop=False)

        # Show the notification
        toast.show()

    def update_min_cooldown_time(
        self, current_min: datetime | None, new_time: str
    ) -> datetime:
        new_time_datetime = datetime.fromisoformat(new_time)
        if new_time_datetime and (
            current_min is None or new_time_datetime < current_min
        ):
            return new_time_datetime
        return current_min

    def cooldown_finished(
        self,
        *,
        item: str | None = None,
        section: str | None = None,
        task_id: str | None = None,
    ) -> None:
        """
        Changes the cooldown_finished parameter to true in data.json for the given section and task_id

        :param item: The item to mark as finished (e.g. "star_battery", "tool_case", "helmet")
        :param section: The section of the task to mark as finished (e.g. "workers", "buildings")
        :param task_id: The ID of the task to mark as finished
        """
        data = MainWindow.load_data()

        if item is not None:
            data[item]["cooldown_finished"] = True
        if section is not None and task_id is not None:
            data[section][task_id]["cooldown_finished"] = True

        MainWindow.save_data(data)

    def run(self):
        """Runs the notification checker"""
        self.check_and_handle_existing_instance()
        self.create_lock_file()
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self.notification_checker())
        finally:
            self.cleanup()

    def check_and_handle_existing_instance(self) -> None:
        """Checks if an instance of the notification manager is already running and kills it if it is"""
        if os.path.exists(LOCK_FILE_PATH):
            # Attempt to stop the old instance
            print(
                "Found an existing Notification Manager instance running. Attempting to stop it."
            )
            try:
                os.remove(LOCK_FILE_PATH)
                print("Successfully stopped the old instance.")
            except:
                print("Failed to stop the old instance.")

    def create_lock_file(self) -> None:
        """Creates a lock file to prevent multiple instances of the notification manager from running"""
        with open(LOCK_FILE_PATH, "w") as lock_file:
            lock_file.write("running")

    def cleanup(self) -> None:
        """Cleans up the lock file and sets the self.running flag to False"""
        if os.path.exists(LOCK_FILE_PATH):
            os.remove(LOCK_FILE_PATH)
        self.running = False


class GlobalSettings(ctk.CTkToplevel):
    def __init__(self):
        super().__init__()

        self.title("Global Settings")
        self.geometry("700x700")
        self.attributes("-topmost", True)

        self.create_window_elements()
        self.process_commands = True  # Initialize a flag to control command processing
        self.set_checkbox_states()

    def create_window_elements(self) -> None:
        """Creates customtkinter window elements for the global settings window"""
        main_title = ctk.CTkLabel(self, text="Global Settings", font=("Arial", 28))
        main_title.place(relx=0.39, rely=0.03)

        self.checkboxes = {}

        frame_notifications = ctk.CTkFrame(self)
        frame_notifications.place(relx=0.25, rely=0.13, relwidth=0.5, relheight=0.34)

        frame_notifications.columnconfigure(1, weight=3)
        frame_notifications.columnconfigure(2, weight=1)

        for i in range(1, 7):
            frame_notifications.rowconfigure(i, weight=1)

        notifications_title = ctk.CTkLabel(
            frame_notifications, text="Notifications", font=("Arial", 22)
        )
        notifications_title.grid(row=1, column=1, columnspan=2)

        # Star Battery
        notifications_star_battery = ctk.CTkLabel(
            frame_notifications, text="Star Battery", font=("Arial", 16)
        )
        notifications_star_battery.grid(row=2, column=1)

        notifications_star_battery_checkbox = ctk.CTkCheckBox(
            frame_notifications,
            text="",
            command=lambda: self.toggle_global_settings("star_battery"),
        )
        notifications_star_battery_checkbox.grid(row=2, column=2, sticky="e")

        self.checkboxes["star_battery"] = notifications_star_battery_checkbox

        # Tool Case
        notifications_tool_case = ctk.CTkLabel(
            frame_notifications, text="Tool Case", font=("Arial", 16)
        )
        notifications_tool_case.grid(row=3, column=1)

        notifications_tool_case_checkbox = ctk.CTkCheckBox(
            frame_notifications,
            text="",
            command=lambda: self.toggle_global_settings("tool_case"),
        )
        notifications_tool_case_checkbox.grid(row=3, column=2, sticky="e")

        self.checkboxes["tool_case"] = notifications_tool_case_checkbox

        # Helmet
        notifications_helmet = ctk.CTkLabel(
            frame_notifications, text="Helmet", font=("Arial", 16)
        )
        notifications_helmet.grid(row=4, column=1)

        notifications_helmet_checkbox = ctk.CTkCheckBox(
            frame_notifications,
            text="",
            command=lambda: self.toggle_global_settings("helmet"),
        )
        notifications_helmet_checkbox.grid(row=4, column=2, sticky="e")

        self.checkboxes["helmet"] = notifications_helmet_checkbox

        # Workers
        notifications_workers = ctk.CTkLabel(
            frame_notifications, text="Workers", font=("Arial", 16)
        )
        notifications_workers.grid(row=5, column=1)

        notifications_workers_checkbox = ctk.CTkCheckBox(
            frame_notifications,
            text="",
            command=lambda: self.toggle_global_settings("workers"),
        )
        notifications_workers_checkbox.grid(row=5, column=2, sticky="e")

        self.checkboxes["workers"] = notifications_workers_checkbox

        # Buildings
        notifications_buildings = ctk.CTkLabel(
            frame_notifications, text="Buildings", font=("Arial", 16)
        )
        notifications_buildings.grid(row=6, column=1)

        notifications_buildings_checkbox = ctk.CTkCheckBox(
            frame_notifications,
            text="",
            command=lambda: self.toggle_global_settings("buildings"),
        )
        notifications_buildings_checkbox.grid(row=6, column=2, sticky="e")

        self.checkboxes["buildings"] = notifications_buildings_checkbox

        # Miscellaneous settings
        frame_miscellaneous_settings = ctk.CTkFrame(self)
        frame_miscellaneous_settings.place(
            relx=0.05, rely=0.53, relwidth=0.9, relheight=0.38
        )

        frame_miscellaneous_settings.columnconfigure(1, weight=5)
        frame_miscellaneous_settings.columnconfigure(2, weight=1)

        for i in range(1, 7):
            frame_miscellaneous_settings.rowconfigure(i, weight=1)

        miscellaneous_settings_title = ctk.CTkLabel(
            frame_miscellaneous_settings, text="Miscellaneous", font=("Arial", 22)
        )
        miscellaneous_settings_title.grid(row=1, column=1, columnspan=2)

        # Auto delete completed tasks on shutdown
        label_auto_delete_completed_tasks = ctk.CTkLabel(
            frame_miscellaneous_settings,
            text="Delete completed worker tasks on closing",
            font=("Arial", 16),
        )
        label_auto_delete_completed_tasks.grid(row=2, column=1)

        checkbox_auto_delete_completed_tasks = ctk.CTkCheckBox(
            frame_miscellaneous_settings,
            text="",
            command=lambda: self.toggle_global_settings("auto_delete_completed_tasks"),
        )
        checkbox_auto_delete_completed_tasks.grid(row=2, column=2, sticky="e")

        self.checkboxes["auto_delete_completed_tasks"] = (
            checkbox_auto_delete_completed_tasks
        )

        # Auto check the checkbox of the instant build time on startup
        label_check_checkbox_instant_build_time_on_startup = ctk.CTkLabel(
            frame_miscellaneous_settings,
            text="Check the checkbox of the instant build time on startup",
            font=("Arial", 16),
        )
        label_check_checkbox_instant_build_time_on_startup.grid(row=3, column=1)

        checkbox_check_checkbox_instant_build_time_on_startup = ctk.CTkCheckBox(
            frame_miscellaneous_settings,
            text="",
            command=lambda: self.toggle_global_settings(
                "check_checkbox_instant_build_time_on_startup"
            ),
        )
        checkbox_check_checkbox_instant_build_time_on_startup.grid(
            row=3, column=2, sticky="e"
        )

        self.checkboxes["check_checkbox_instant_build_time_on_startup"] = (
            checkbox_check_checkbox_instant_build_time_on_startup
        )

        # Notifications on startup
        label_disable_notifications_during_startup = ctk.CTkLabel(
            frame_miscellaneous_settings,
            text="Temporarily disable notifications during startup",
            font=("Arial", 16),
        )
        label_disable_notifications_during_startup.grid(row=4, column=1)

        checkbox_disable_notifications_during_startup = ctk.CTkCheckBox(
            frame_miscellaneous_settings,
            text="",
            command=lambda: self.toggle_global_settings(
                "disable_notifications_during_startup"
            ),
        )
        checkbox_disable_notifications_during_startup.grid(row=4, column=2, sticky="e")

        self.checkboxes["disable_notifications_during_startup"] = (
            checkbox_disable_notifications_during_startup
        )

        # Run notifications in background
        label_run_notifications_in_background = ctk.CTkLabel(
            frame_miscellaneous_settings,
            text="Get notifications when the program is closed (Restart required)",
            font=("Arial", 16),
        )
        label_run_notifications_in_background.grid(row=5, column=1)

        checkbox_run_notifications_in_background = ctk.CTkCheckBox(
            frame_miscellaneous_settings,
            text="",
            command=lambda: self.toggle_global_settings(
                "run_notifications_in_background"
            ),
        )
        checkbox_run_notifications_in_background.grid(row=5, column=2, sticky="e")

        self.checkboxes["run_notifications_in_background"] = (
            checkbox_run_notifications_in_background
        )

        # Show command window (debug)
        label_show_command_window = ctk.CTkLabel(
            frame_miscellaneous_settings,
            text="Show command window (Debug)",
            font=("Arial", 16),
        )
        label_show_command_window.grid(row=6, column=1)

        checkbox_show_command_window = ctk.CTkCheckBox(
            frame_miscellaneous_settings,
            text="",
            command=lambda: self.toggle_global_settings("show_command_window"),
        )
        checkbox_show_command_window.grid(row=6, column=2, sticky="e")

        self.checkboxes["show_command_window"] = checkbox_show_command_window

    def set_checkbox_states(self):
        """Sets the state of the checkboxes to its corresponding value in settings.json without triggering commands."""
        settings = MainWindow.load_settings()
        self.process_commands = False  # Temporarily disable command processing
        for entry, value in settings["global_settings"].items():
            if value:
                checkbox = self.checkboxes[entry]
                checkbox.select()
        self.process_commands = True  # Re-enable command processing

    def toggle_global_settings(self, setting_key):
        """Toggle the global settings, processing only if triggered by user action."""
        settings = MainWindow.load_settings()
        if self.process_commands:  # Process only if allowed
            current_value = settings["global_settings"][setting_key]
            settings["global_settings"][setting_key] = not current_value
            # Save the settings
            MainWindow.save_settings(settings)

            # Shows or hides the command window when that setting is changed
            if setting_key == "show_command_window":
                MainWindow.toggle_command_window(
                    "show" if settings["global_settings"][setting_key] else "hide"
                )


class PlanetsSettings(ctk.CTkToplevel):
    def __init__(self):
        super().__init__()

        self.title("Planets Settings")
        self.geometry("700x700")
        self.attributes("-topmost", True)

        self.settings = MainWindow.load_settings()

        self.create_window_elements()
        self.process_commands = True  # Initialize a flag to control command processing
        self.set_switch_and_combobox_states()

    def create_window_elements(self):
        """Creates customtkinter window elements for the planets settings window"""
        main_title = ctk.CTkLabel(self, text="Planets Settings", font=("Arial", 20))
        main_title.place(relx=0.4, rely=0.03)

        frame_colonies = ctk.CTkFrame(self, fg_color="#242424")
        frame_colonies.place(relx=0.05, rely=0.1, relwidth=0.9, relheight=0.8)

        for i in range(1, 12):
            frame_colonies.rowconfigure(i, weight=1)

        frame_colonies.columnconfigure(1, weight=1)
        frame_colonies.columnconfigure(2, weight=1)
        frame_colonies.columnconfigure(3, weight=1)

        self.switches_and_comboboxes = {}

        combobox_options = [
            "Planet_blue.png",
            "Planet_green.png",
            "Planet_red.png",
            "Planet_violet.png",
            "Planet_white.png",
            "Planet_yellow.png",
        ]

        for i in range(1, 12):
            switch = ctk.CTkSwitch(
                frame_colonies,
                text=f"        Colony {i}",
                font=("Arial", 16),
                text_color="grey",
                command=lambda i=i: self.toggle_colony(f"colony_{i}"),
            )
            switch.grid(row=i, column=1)

            self.planet = self.settings["planets_settings"][f"colony_{i}"][
                "planet_image"
            ]
            try:
                if not self.settings["planets_settings"][f"colony_{i}"]["enabled"]:
                    self.planet = self.planet.replace(".png", "_greyscale.png")

                image_planet = ctk.CTkImage(
                    Image.open(
                        Path(
                            PLANETS_IMAGES_PATH,
                            self.planet,
                        ),
                    ),
                    size=(40, 40),
                )
            except:
                image_planet = None
            label_image_planet = ctk.CTkLabel(
                frame_colonies, image=image_planet, text=""
            )
            label_image_planet.grid(row=i, column=2)

            combobox = ctk.CTkComboBox(
                frame_colonies,
                values=combobox_options,
                command=lambda planet, i=i: self.select_colony_image(
                    planet, f"colony_{i}"
                ),
                state="disabled",
            )
            combobox.grid(row=i, column=3)

            # Store the switch and combobox in the dictionary
            self.switches_and_comboboxes[f"colony_{i}"] = (
                switch,
                label_image_planet,
                combobox,
            )

    def set_switch_and_combobox_states(self):
        """Sets the state of the switches to its corresponding value in settings.json without triggering the toggle_colony function."""
        self.process_commands = False  # Temporarily disable command processing
        for entry in self.settings["planets_settings"]:
            if entry != "main_planet":
                # Check if the switch was on previously
                if self.settings["planets_settings"][entry]["enabled"]:
                    self.switches_and_comboboxes[entry][0].select()
                    self.switches_and_comboboxes[entry][0].configure(text_color="white")
                    self.switches_and_comboboxes[entry][2].configure(state="readonly")
                    self.switches_and_comboboxes[entry][2].set(
                        self.settings["planets_settings"][entry]["planet_image"]
                    )
                else:
                    self.switches_and_comboboxes[entry][2].configure(state="readonly")
                    self.switches_and_comboboxes[entry][2].set(
                        self.settings["planets_settings"][entry]["planet_image"]
                    )
                    self.switches_and_comboboxes[entry][2].configure(state="disabled")

        self.process_commands = True  # Re-enable command processing

    def toggle_colony(self, colony):
        """
        Changing state of the combobox when the switch is triggered, and changes the value of the switch in settings.json only when the user triggers the switch.

        :param colony: The colony to toggle (e.g., colony_1, colony_2, .... , colony_11)
        """
        switch, label_image_planet, combobox = self.switches_and_comboboxes[colony]
        planet_image = self.settings["planets_settings"][colony][
            "planet_image"
        ]  # Define planet_image here to ensure it's available throughout

        if switch.get() == 1:
            # Switch is on
            switch.configure(text_color="white")
            combobox.configure(state="readonly")
            # Ensure planet_image is not just a directory path
            if planet_image:
                image_path = Path(PLANETS_IMAGES_PATH, planet_image)
                if image_path.is_file():  # Check if the path points to a file
                    image_planet = ctk.CTkImage(Image.open(image_path), size=(40, 40))
                    label_image_planet.configure(image=image_planet)
        else:
            # Switch is off
            switch.configure(text_color="grey")  # Change text color to grey
            combobox.configure(state="disabled")
            if planet_image:
                # Set the image to a greyed-out version
                planet_image_grey = planet_image.replace(".png", "_greyscale.png")
                grey_image_path = Path(PLANETS_IMAGES_PATH, planet_image_grey)
                if grey_image_path.is_file():  # Check if the path points to a file
                    grey_image_planet = ctk.CTkImage(
                        Image.open(grey_image_path), size=(40, 40)
                    )
                    label_image_planet.configure(image=grey_image_planet)

        if self.process_commands:  # Process only if allowed
            current_value = self.settings["planets_settings"][colony]["enabled"]
            self.settings["planets_settings"][colony]["enabled"] = not current_value
            # Save the settings
            MainWindow.save_settings(self.settings)
            MainWindow.available_planets(
                main_window
            )  # Calling available_planets like this prevents the error from not having the variable self from MainWindow

    def select_colony_image(self, planet, colony):
        """Save the selected planet image to settings.json and display that image in "label_image_planet"."""

        # Save the selected planet image to settings.json
        self.settings["planets_settings"][colony]["planet_image"] = planet
        MainWindow.save_settings(self.settings)

        # Display the image
        image_planet = ctk.CTkImage(
            Image.open(Path(PLANETS_IMAGES_PATH, planet)), size=(40, 40)
        )
        self.switches_and_comboboxes[colony][1].configure(image=image_planet)


class MainWindow(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Galaxy Life Notifier")
        self.geometry("1600x1000")

        # Check if the command window needs to be shown or hidden
        settings = self.load_settings()
        self.toggle_command_window(
            "show" if settings["global_settings"]["show_command_window"] else "hide"
        )

        self.create_window_elements()
        self.start_notification_manager()

    def start_notification_manager(self):
        self.notification_manager = NotificationManager()

        def run_notifier():
            asyncio.run(self.notification_manager.run())

        notifier_thread = threading.Thread(target=run_notifier)
        settings = self.load_settings()
        notifier_thread.daemon = not settings["global_settings"][
            "run_notifications_in_background"
        ]
        notifier_thread.start()

    def create_window_elements(self):
        """Creates customtkinter window elements for the main window"""
        main_title_image = ctk.CTkImage(
            Image.open(Path(MAIN_IMAGES_PATH, "Starling_Postman_AI_Upscaled.png")),
            size=(75, 75),
        )
        main_title = ctk.CTkLabel(
            self,
            text="Galaxy Life Notifier",
            font=("Arial", 32),
            image=main_title_image,
            compound="left",
        )
        main_title.place(relx=0.41, rely=0.01)

        ## Global Settings Button
        image_button_settings_global = ctk.CTkImage(
            Image.open(Path(MAIN_IMAGES_PATH, "dark_mode_options_icon.png")),
            size=(25, 25),
        )
        button_settings_global = ctk.CTkButton(
            self,
            text="",
            fg_color="#2b2b2b",
            image=image_button_settings_global,
            command=GlobalSettings,
        )
        button_settings_global.place(
            relx=0.85, rely=0.03, relwidth=0.04, relheight=0.04
        )

        # Items Frame
        frame_items = ctk.CTkFrame(self)
        frame_items.place(relx=0.03, rely=0.1, relwidth=0.46, relheight=0.25)

        frame_items.columnconfigure(1, weight=1)
        frame_items.columnconfigure(2, weight=1)
        frame_items.columnconfigure(3, weight=1)

        frame_items.rowconfigure(1, weight=1)
        frame_items.rowconfigure(2, weight=1)
        frame_items.rowconfigure(3, weight=1)
        frame_items.rowconfigure(4, weight=1)

        ## Items Frame Title
        image_label_items_title = ctk.CTkImage(
            Image.open(Path(MAIN_IMAGES_PATH, "Starlings_with_Star_Battery.png")),
            size=(90, 60),
        )
        label_items_title = ctk.CTkLabel(
            frame_items,
            text=" Items",
            font=("Arial", 28),
            image=image_label_items_title,
            compound="left",
        )
        label_items_title.grid(column=1, row=1, columnspan=3)

        ## Star Battery
        image_star_battery = ctk.CTkImage(
            Image.open(Path(MAIN_IMAGES_PATH, "star_battery.png")),
            size=(40, 40),
        )
        label_star_battery = ctk.CTkLabel(
            frame_items,
            text=" Star Battery",
            font=("Arial", 16),
            width=200,  # used to get an equal offset from the left of the frame for label_star_battery, label_tool_case, and label_helmet
            image=image_star_battery,
            compound="left",
        )
        label_star_battery.grid(column=1, row=2, sticky="w")

        self.label_star_battery_cooldown = ctk.CTkLabel(frame_items, font=("Arial", 16))
        self.label_star_battery_cooldown.grid(column=2, row=2)

        button_star_battery = ctk.CTkButton(
            frame_items,
            text="Start Cooldown Timer",
            font=("Arial", 16),
            command=lambda: self.set_item_cooldown("star_battery"),
        )
        button_star_battery.grid(column=3, row=2)

        ## Tool Case
        image_tool_case = ctk.CTkImage(
            Image.open(Path(MAIN_IMAGES_PATH, "tool_case.png")),
            size=(40, 40),
        )
        label_tool_case = ctk.CTkLabel(
            frame_items,
            text=" Tool Case",
            font=("Arial", 16),
            width=190,  # used to get an equal offset from the left of the frame for label_star_battery, label_tool_case, and label_helmet
            image=image_tool_case,
            compound="left",
        )
        label_tool_case.grid(column=1, row=3, sticky="w")

        self.label_tool_case_cooldown = ctk.CTkLabel(frame_items, font=("Arial", 16))
        self.label_tool_case_cooldown.grid(column=2, row=3)

        button_tool_case = ctk.CTkButton(
            frame_items,
            text="Start Cooldown Timer",
            font=("Arial", 16),
            command=lambda: self.set_item_cooldown("tool_case"),
        )
        button_tool_case.grid(column=3, row=3)

        ## Helmet
        image_helmet = ctk.CTkImage(
            Image.open(Path(MAIN_IMAGES_PATH, "helmet.png")),
            size=(40, 40),
        )
        label_helmet = ctk.CTkLabel(
            frame_items,
            text=" Helmet",
            font=("Arial", 16),
            width=170,  # used to get an equal offset from the left of the frame for label_star_battery, label_tool_case, and label_helmet
            image=image_helmet,
            compound="left",
        )
        label_helmet.grid(column=1, row=4, sticky="w")

        self.label_helmet_cooldown = ctk.CTkLabel(frame_items, font=("Arial", 16))
        self.label_helmet_cooldown.grid(column=2, row=4)

        button_helmet = ctk.CTkButton(
            frame_items,
            text="Start Cooldown Timer",
            font=("Arial", 16),
            command=lambda: self.set_item_cooldown("helmet"),
        )
        button_helmet.grid(column=3, row=4)

        # Set the text of the items cooldown labels
        for item in ["star_battery", "tool_case", "helmet"]:
            self.set_item_text(item)

        # Workers Frame
        self.frame_workers = ctk.CTkFrame(self, corner_radius=0)
        self.frame_workers.place(relx=0.52, rely=0.1, relwidth=0.46, relheight=0.1)

        self.frame_workers.rowconfigure(1, weight=1)
        self.frame_workers.rowconfigure(2, weight=1)

        self.frame_workers.columnconfigure(1, weight=5)
        self.frame_workers.columnconfigure(2, weight=5)
        self.frame_workers.columnconfigure(3, weight=1)
        self.frame_workers.columnconfigure(4, weight=1)

        ## Workers Frame Title
        image_workers_title = ctk.CTkImage(
            Image.open(Path(MAIN_IMAGES_PATH, "Worker.png")),
            size=(60, 60),
        )
        label_workers_title = ctk.CTkLabel(
            self.frame_workers,
            text=" Workers",
            font=("Arial", 28),
            image=image_workers_title,
            compound="left",
        )
        label_workers_title.grid(row=1, column=1, columnspan=4)

        ## Planets Settings Button
        image_button_settings_planets = ctk.CTkImage(
            Image.open(Path(MAIN_IMAGES_PATH, "dark_mode_options_icon.png")),
            size=(20, 20),
        )
        button_settings_planets = ctk.CTkButton(
            self.frame_workers,
            text="Planets Settings",
            font=("Arial", 16),
            fg_color="#2b2b2b",
            image=image_button_settings_planets,
            compound="left",
            command=PlanetsSettings,
        )
        button_settings_planets.grid(row=1, column=4)

        ## Workers add task environment
        self.label_image_planet_workers = ctk.CTkLabel(
            self.frame_workers, text="", image=None
        )
        self.label_image_planet_workers.grid(row=2, column=1, sticky="w")

        self.combobox_planet_workers = ctk.CTkComboBox(
            self.frame_workers,
            width=110,
            state="readonly",
            values=None,
            command=lambda planet, label_image=self.label_image_planet_workers: self.select_planet_image(
                planet, label_image
            ),
        )  # Values are defined in "def available_planets"
        self.combobox_planet_workers.grid(row=2, column=1)

        self.textbox_hours_workers = ctk.CTkEntry(
            self.frame_workers, placeholder_text="Hours", width=80
        )
        self.textbox_hours_workers.grid(row=2, column=2, sticky="w")
        self.textbox_hours_workers.bind(
            "<Right>",
            lambda event, context="workers": self.focus_on_minutes(event, context),
        )
        self.textbox_hours_workers.bind(
            "<Return>",
            lambda event, context="workers": self.add_task_wrapper(event, context),
        )

        self.textbox_minutes_workers = ctk.CTkEntry(
            self.frame_workers, placeholder_text="Minutes (0-59)", width=100
        )
        self.textbox_minutes_workers.grid(row=2, column=2, sticky="e")
        self.textbox_minutes_workers.bind(
            "<Left>",
            lambda event, context="workers": self.focus_on_hours(event, context),
        )
        self.textbox_minutes_workers.bind(
            "<Return>",
            lambda event, context="workers": self.add_task_wrapper(event, context),
        )

        self.checkbox_instant_build_time = ctk.CTkCheckBox(
            self.frame_workers,
            checkbox_width=20,
            checkbox_height=20,
            text="Subtract Instant Build Time",
            font=("Arial", 11),
        )
        self.checkbox_instant_build_time.grid(row=2, column=3)

        # Check if self.checkbox_instant_build_time needs to be selected on startup
        settings = self.load_settings()
        (
            self.checkbox_instant_build_time.select()
            if settings["global_settings"][
                "check_checkbox_instant_build_time_on_startup"
            ]
            else self.checkbox_instant_build_time.deselect()
        )

        button_add_worker_task = ctk.CTkButton(
            self.frame_workers, text="Add", command=self.add_workers_task
        )
        button_add_worker_task.grid(row=2, column=4)

        ## Workers Tasks Display
        self.frame_workers_tasks = ctk.CTkScrollableFrame(self, corner_radius=0)
        self.frame_workers_tasks.place(
            relx=0.52, rely=0.2, relwidth=0.46, relheight=0.75
        )
        self.frame_workers_tasks.columnconfigure(1, weight=1)
        self.frame_workers_tasks.columnconfigure(2, weight=1)
        self.frame_workers_tasks.columnconfigure(3, weight=1)

        # Make all the elements for workers tasks frame
        self.workers_tasks_display()

        # Buildings Frame
        self.frame_buildings = ctk.CTkFrame(self, corner_radius=0)
        self.frame_buildings.place(relx=0.03, rely=0.37, relwidth=0.46, relheight=0.1)

        self.frame_buildings.rowconfigure(1, weight=1)
        self.frame_buildings.rowconfigure(2, weight=1)

        self.frame_buildings.columnconfigure(1, weight=1)
        self.frame_buildings.columnconfigure(2, weight=1)
        self.frame_buildings.columnconfigure(3, weight=2)
        self.frame_buildings.columnconfigure(4, weight=1)

        ## Buildings Frame Title
        image_buildings_title = ctk.CTkImage(
            Image.open(Path(MAIN_IMAGES_PATH, "Warp_Gate.png")),
            size=(60, 60),
        )
        label_buildings_title = ctk.CTkLabel(
            self.frame_buildings,
            text=" Buildings",
            font=("Arial", 28),
            image=image_buildings_title,
            compound="left",
        )
        label_buildings_title.grid(row=1, column=1, columnspan=4)

        ## Planets Settings Button
        image_button_settings_planets = ctk.CTkImage(
            Image.open(Path(MAIN_IMAGES_PATH, "dark_mode_options_icon.png")),
            size=(20, 20),
        )
        button_settings_planets = ctk.CTkButton(
            self.frame_buildings,
            text="Planets Settings",
            font=("Arial", 16),
            fg_color="#2b2b2b",
            image=image_button_settings_planets,
            compound="left",
            command=PlanetsSettings,
        )
        button_settings_planets.grid(row=1, column=4)

        ## Buildings add tasks environment
        self.label_image_planet_buildings = ctk.CTkLabel(
            self.frame_buildings, text="", image=None
        )
        self.label_image_planet_buildings.grid(row=2, column=1, sticky="w")

        self.combobox_planet_buildings = ctk.CTkComboBox(
            self.frame_buildings,
            width=110,
            state="readonly",
            values=None,
            command=lambda planet, label_image=self.label_image_planet_buildings: self.select_planet_image(
                planet, label_image
            ),
        )  # Values are defined in "def available_planets"
        self.combobox_planet_buildings.grid(row=2, column=1, sticky="e")

        self.combobox_buildings = ctk.CTkComboBox(
            self.frame_buildings,
            width=125,
            state="readonly",
            values="",  # Values get defined in def update_buildings_options
        )
        self.combobox_buildings.grid(row=2, column=2)

        self.textbox_hours_buildings = ctk.CTkEntry(
            self.frame_buildings, placeholder_text="Hours", width=90
        )
        self.textbox_hours_buildings.grid(row=2, column=3, sticky="w")
        self.textbox_hours_buildings.bind(
            "<Right>",
            lambda event, context="buildings": self.focus_on_minutes(event, context),
        )
        self.textbox_hours_buildings.bind(
            "<Return>",
            lambda event, context="buildings": self.add_task_wrapper(event, context),
        )

        self.textbox_minutes_buildings = ctk.CTkEntry(
            self.frame_buildings, placeholder_text="Minutes (0-59)", width=100
        )
        self.textbox_minutes_buildings.grid(row=2, column=3, sticky="e")
        self.textbox_minutes_buildings.bind(
            "<Left>",
            lambda event, context="buildings": self.focus_on_hours(event, context),
        )
        self.textbox_minutes_buildings.bind(
            "<Return>",
            lambda event, context="buildings": self.add_task_wrapper(event, context),
        )

        button_add_building_task = ctk.CTkButton(
            self.frame_buildings, text="Add", command=self.add_buildings_task
        )
        button_add_building_task.grid(row=2, column=4)

        ## Buildings Tasks Display
        self.frame_buildings_tasks = ctk.CTkScrollableFrame(self, corner_radius=0)
        self.frame_buildings_tasks.place(
            relx=0.03, rely=0.47, relwidth=0.46, relheight=0.48
        )
        self.frame_buildings_tasks.columnconfigure(1, weight=1)
        self.frame_buildings_tasks.columnconfigure(2, weight=1)
        self.frame_buildings_tasks.columnconfigure(3, weight=1)
        self.frame_buildings_tasks.columnconfigure(4, weight=1)

        # Make all the elements for buildings tasks frame
        self.buildings_tasks_display()

        # Initialize the values for the comboboxes for selecting a planet
        self.available_planets()

    def focus_on_minutes(self, event, context: str) -> None:
        """Focuses on the minutes textbox of the workers or buildings section"""
        if context == "workers":
            self.textbox_minutes_workers.focus_set()
        elif context == "buildings":
            self.textbox_minutes_buildings.focus_set()

    def focus_on_hours(self, event, context: str) -> None:
        """Focuses on the hours textbox of the workers or buildings section"""
        if context == "workers":
            self.textbox_hours_workers.focus_set()
        elif context == "buildings":
            self.textbox_hours_buildings.focus_set()

    def add_task_wrapper(self, event, context: str) -> None:
        """Returns to the hours textbox of the workers or buildings section when a task is added"""
        if context == "workers":
            self.add_workers_task()
            self.focus_on_hours(event=None, context="workers")
        elif context == "buildings":
            self.add_buildings_task()
            self.focus_on_hours(event=None, context="buildings")

    def update_item_label(self, item_type: str, text: str) -> None:
        """
        Updates the text of an item's cooldown label.

        :param: item_type: The type of the item (e.g., "star_battery", "tool_case", "helmet")
        :param: text: The new text for the item's cooldown label
        """
        try:
            label_map = {
                "star_battery": self.label_star_battery_cooldown,
                "tool_case": self.label_tool_case_cooldown,
                "helmet": self.label_helmet_cooldown,
            }
            if item_type in label_map:
                label_map[item_type].configure(text=text)
        except KeyError:
            raise KeyError(
                f"Item type '{item_type}' not recognized. Only valuable options are {label_map.keys()}"
            )

    def set_item_text(self, item_type: str):
        """
        Generates the text for an item based on its cooldown.

        :param item_type: The type of the item (e.g., "star_battery", "tool_case", "helmet")
        """
        try:
            data = self.load_data()
            cooldown_date = data[item_type].get("cooldown")
            if cooldown_date is None:
                text = "Cooldown date not available."
            elif self.compare_to_current_time(cooldown_date):
                text = (
                    "Ready to collect! (Compact Houses)"
                    if item_type == "helmet"
                    else "Ready to collect! (Help Friends)"
                )
            else:
                cooldown_date_datetime = datetime.fromisoformat(cooldown_date)
                text = f"Ready on {cooldown_date_datetime:%d-%m-%Y %H:%M}"

            self.update_item_label(item_type, text)

        except Exception as e:
            print(f"An error occurred: {str(e)}")
            self.update_item_label(
                item_type, "Click the button when you collected this item"
            )

    def set_item_cooldown(self, item_type: str) -> None:
        """
        Sets the cooldown for a given item based on its type and updates the corresponding label.

        :param item_type: The type of the item (e.g., "star_battery", "tool_case", "helmet")
        """
        cooldown_hours = {
            "star_battery": 11,
            "tool_case": 23,
            "helmet": 35,
        }
        data = self.load_data()
        if item_type in cooldown_hours:
            hours = cooldown_hours[item_type]
            new_time = (datetime.now() + timedelta(hours=hours)).isoformat()

            data[item_type]["cooldown"] = new_time
            data[item_type]["cooldown_finished"] = False

            self.save_data(data)
            self.update_item_label(item_type, self.set_item_text(item_type))
        else:
            print(f"Cooldown hours not defined for {item_type}.")

    def available_planets(self) -> list[str]:
        """
        Checks in settings.json which colonies are available to choose from.

        :return: list of available planets
        """
        settings = self.load_settings()

        planet_names = []
        for key, value in settings["planets_settings"].items():
            if value["enabled"]:
                planet_name = key.replace("_", " ").title()
                planet_names.append(planet_name)

        self.combobox_planet_workers.configure(values=planet_names)
        self.combobox_planet_buildings.configure(values=planet_names)

    def add_workers_task(self) -> None:
        """Adds a worker task to data.json if all values have passed the error checking"""
        planet = self.combobox_planet_workers.get()
        hours = (
            int(self.textbox_hours_workers.get())
            if self.textbox_hours_workers.get()
            else 0
        )
        minutes = (
            int(self.textbox_minutes_workers.get())
            if self.textbox_minutes_workers.get()
            else 0
        )

        # Reset previous error border colors
        self.textbox_hours_workers.configure(border_color="#565b5e")
        self.textbox_minutes_workers.configure(border_color="#565b5e")
        self.combobox_planet_workers.configure(
            border_color="#565b5e", button_color="#565b5e"
        )

        if planet == "":
            self.combobox_planet_workers.configure(
                border_color="red", button_color="red"
            )
        elif minutes == 0 and hours == 0:
            self.textbox_hours_workers.configure(border_color="red")
            self.textbox_minutes_workers.configure(border_color="red")
        elif minutes >= 60:
            self.textbox_minutes_workers.configure(border_color="red")
        else:
            data = self.load_data()

            # Generate the task ID based on the planet and existing tasks
            planet_snake_case = self.convert_to_snake_case(planet)
            existing_ids = [
                int(task_id.split("_")[-1])
                for task_id, task_info in data["workers"].items()
                if task_info["planet"] == planet
            ]
            next_id = max(existing_ids) + 1 if existing_ids else 1
            task_id = f"{planet_snake_case}_{next_id}"

            if self.checkbox_instant_build_time.get() == 1:
                input_time = timedelta(hours=hours, minutes=minutes)
                if input_time >= timedelta(minutes=10):
                    new_time = (
                        datetime.now() + input_time - timedelta(minutes=5)
                    ).isoformat()
                else:
                    instant_build_time = (
                        input_time - timedelta(minutes=5)
                        if input_time > timedelta(minutes=5)
                        else timedelta(minutes=0)
                    )
                    new_time = (datetime.now() + instant_build_time).isoformat()
            else:
                new_time = (
                    datetime.now() + timedelta(hours=hours, minutes=minutes)
                ).isoformat()

            new_entry = {
                "cooldown": new_time,
                "planet": planet,
                "cooldown_finished": False,
            }

            # Convert workers data to a list of tuples for sorting
            workers_list = [
                (task_id, task_info) for task_id, task_info in data["workers"].items()
            ]
            # Add the new task's cooldown_datetime for comparison
            new_entry["cooldown_datetime"] = datetime.fromisoformat(
                new_entry["cooldown"]
            )
            # Find the correct position to insert the new task
            insert_index = 0
            for i, (_, task_info) in enumerate(workers_list):
                task_info["cooldown_datetime"] = datetime.fromisoformat(
                    task_info["cooldown"]
                )
                if new_entry["cooldown_datetime"] < task_info["cooldown_datetime"]:
                    insert_index = i
                    break
                insert_index = (
                    i + 1
                )  # Update insert_index to insert at the end if no earlier cooldown is found

            # Insert the new task into the list
            workers_list.insert(insert_index, (task_id, new_entry))

            # Convert the list back to a dictionary and update the data
            data["workers"] = {
                task_id: task_info for task_id, task_info in workers_list
            }

            # Clean up temporary keys
            for task_info in data["workers"].values():
                task_info.pop("cooldown_datetime", None)

            if self.textbox_hours_workers.get() != "":
                self.textbox_hours_workers.delete(0, 100)
            if self.textbox_minutes_workers.get() != "":
                self.textbox_minutes_workers.delete(0, 2)

            self.save_data(data)
            self.workers_tasks_display()

    def remove_workers_task(self, task_id: str) -> None:
        """
        Removes a specified worker's task from data.json

        :param task_id: The id of the entry which needs to be removed
        """
        data = self.load_data()

        # Check if the task ID exists in the dictionary
        if task_id in data["workers"]:
            # Delete the specified worker's task
            del data["workers"][task_id]
        else:
            print(
                f"Workers Task with the following id not found in data.json: {task_id}"
            )

        self.save_data(data)
        self.workers_tasks_display()

    def select_planet_image(self, planet: str, label_image: ctk.CTkLabel) -> None:
        """
        Selects the image of the planet
        :param planet: The name of the planet
        :param label_image: The label where the image of the planet must be displayed
        """
        settings = self.load_settings()

        planet_snake_case = self.convert_to_snake_case(planet)
        image_planet = ctk.CTkImage(
            Image.open(
                Path(
                    PLANETS_IMAGES_PATH,
                    settings["planets_settings"][planet_snake_case]["planet_image"],
                )
            ),
            size=(40, 40),
        )
        label_image.configure(image=image_planet)

        # Update the buildings options if a planet was selected in the combobox of the buildings section
        if label_image == self.label_image_planet_buildings:
            self.update_buildings_options()

    def workers_tasks_display(self) -> None:
        """
        Display workers' tasks based on the loaded data and settings.
        """
        data = self.load_data()
        settings = self.load_settings()

        # Clear existing widgets in frame_workers_tasks
        for widget in self.frame_workers_tasks.winfo_children():
            widget.destroy()

        # Now recreate the widgets based on the current data
        for i, (task_id, task_info) in enumerate(data["workers"].items(), start=1):
            self.frame_workers_tasks.rowconfigure(i, weight=1)

            planet_name = task_info["planet"]
            planet = self.convert_to_snake_case(planet_name)
            image_path = Path(
                PLANETS_IMAGES_PATH,
                settings["planets_settings"][planet]["planet_image"],
            )
            image_planet = ctk.CTkImage(
                Image.open(image_path),
                size=(40, 40),
            )
            label_planet = ctk.CTkLabel(
                self.frame_workers_tasks,
                text=f" {planet_name}",
                font=("Arial", 16),
                image=image_planet,
                compound="left",
            )
            label_planet.grid(row=i, column=1)

            label_cooldown = ctk.CTkLabel(
                self.frame_workers_tasks,
                text=self.set_workers_cooldown_text(task_id),
                font=("Arial", 16),
            )
            label_cooldown.grid(row=i, column=2)

            image_trashcan_path = Path(MAIN_IMAGES_PATH, "dark_mode_trash_can.png")
            image_trashcan = ctk.CTkImage(
                Image.open(image_trashcan_path),
                size=(20, 20),
            )

            button_remove_task = ctk.CTkButton(
                self.frame_workers_tasks,
                text="",
                fg_color="red",
                hover_color="dark red",
                width=30,
                image=image_trashcan,
                command=lambda task_id=task_id: self.remove_workers_task(task_id),
            )
            button_remove_task.grid(row=i, column=3)

    def set_workers_cooldown_text(self, task_id: str) -> str:
        """
        Sets the cooldown text of the label corresponding to the workers task
        :param task_id: The id of the task
        """
        data = self.load_data()

        cooldown_date = data["workers"][task_id]["cooldown"]

        if self.compare_to_current_time(cooldown_date):
            return "Upgrade Finished!"
        else:
            cooldown_date_datetime = datetime.fromisoformat(cooldown_date)
            return f"Working until {cooldown_date_datetime:%d-%m-%Y %H:%M}"

    def convert_to_snake_case(self, text: str) -> str:
        """
        Converts given text to snake case

        :param text: Text to be converted to snake case
        :return: Snake case text
        """
        words = text.split()
        snake_case_words = [word.lower() for word in words]
        snake_case_text = "_".join(snake_case_words)
        return snake_case_text

    def update_buildings_options(self) -> None:
        """Updates the options which can be selected in the combobox self.combobox_buildings"""
        selected_planet = self.combobox_planet_buildings.get()
        buildings_values = ["Laboratory", "Training Camp", "Factory", "StarPort"]

        # Adds the option "Refinery" when the selected planet is "Main Planet"
        if selected_planet == "Main Planet":
            buildings_values.insert(1, "Refinery")

        # Prevents "Refinery" from being selected when switching from "Main Planet" to a different planet
        if (
            selected_planet != "Main Planet"
            and self.combobox_buildings.get() == "Refinery"
        ):
            self.combobox_buildings.set("")

        self.combobox_buildings.configure(values=buildings_values)

    def add_buildings_task(self):
        """Adds a building task to data.json if all values have passed the error checking"""
        planet = self.combobox_planet_buildings.get()
        building = self.combobox_buildings.get()
        hours = (
            int(self.textbox_hours_buildings.get())
            if self.textbox_hours_buildings.get()
            else 0
        )
        minutes = (
            int(self.textbox_minutes_buildings.get())
            if self.textbox_minutes_buildings.get()
            else 0
        )

        # Reset previous error border colors
        self.textbox_hours_buildings.configure(border_color="#565b5e")
        self.textbox_minutes_buildings.configure(border_color="#565b5e")
        self.combobox_planet_buildings.configure(
            border_color="#565b5e", button_color="#565b5e"
        )
        self.combobox_buildings.configure(
            border_color="#565b5e", button_color="#565b5e"
        )

        if planet == "":
            self.combobox_planet_buildings.configure(
                border_color="red", button_color="red"
            )
        elif building == "":
            self.combobox_buildings.configure(border_color="red", button_color="red")
        elif minutes == 0 and hours == 0:
            self.textbox_hours_buildings.configure(border_color="red")
            self.textbox_minutes_buildings.configure(border_color="red")
        elif minutes >= 60:
            self.textbox_minutes_buildings.configure(border_color="red")
        else:
            data = self.load_data()

            new_time = (
                datetime.now() + timedelta(hours=hours, minutes=minutes)
            ).isoformat()

            # Generate the task ID based on the planet, building, and existing tasks
            planet_building_snake_case = f"{self.convert_to_snake_case(planet)}_{self.convert_to_snake_case(building)}"
            existing_ids = [
                int(task_id.split("_")[-1])
                for task_id in data["buildings"].keys()
                if task_id.startswith(planet_building_snake_case)
            ]
            next_id = max(existing_ids) + 1 if existing_ids else 1
            task_id = f"{planet_building_snake_case}_{next_id}"

            new_entry = {
                "cooldown": new_time,
                "planet": planet,
                "building": building,
                "cooldown_finished": False,
            }

            # Convert buildings data to a list of tuples for sorting
            buildings_list = [
                (task_id, task_info) for task_id, task_info in data["buildings"].items()
            ]
            # Add the new task's cooldown_datetime for comparison
            new_entry["cooldown_datetime"] = datetime.fromisoformat(
                new_entry["cooldown"]
            )
            # Find the correct position to insert the new task
            insert_index = 0
            for i, (_, task_info) in enumerate(buildings_list):
                task_info["cooldown_datetime"] = datetime.fromisoformat(
                    task_info["cooldown"]
                )
                if new_entry["cooldown_datetime"] < task_info["cooldown_datetime"]:
                    insert_index = i
                    break
                insert_index = (
                    i + 1
                )  # Update insert_index to insert at the end if no earlier cooldown is found

            # Insert the new task into the list
            buildings_list.insert(insert_index, (task_id, new_entry))

            # Convert the list back to a dictionary and update the data
            data["buildings"] = {
                task_id: task_info for task_id, task_info in buildings_list
            }

            # Clean up temporary keys
            for task_info in data["buildings"].values():
                task_info.pop("cooldown_datetime", None)

            if self.textbox_hours_buildings.get() != "":
                self.textbox_hours_buildings.delete(0, 100)
            if self.textbox_minutes_buildings.get() != "":
                self.textbox_minutes_buildings.delete(0, 2)

            self.save_data(data)
            self.buildings_tasks_display()

    def remove_buildings_task(self, task_id):
        """
        Removes a specified building task from data.json

        :param task_id: The id of the entry which needs to be removed
        """
        data = self.load_data()

        # Check if the task ID exists in the dictionary
        if task_id in data["buildings"]:
            # Delete the specified building task
            del data["buildings"][task_id]
            print(f"Removed task {task_id} from data.json")
        else:
            print(
                f"Buildings Task with the following id not found in data.json: {task_id}"
            )

        self.save_data(data)
        self.buildings_tasks_display()

    def buildings_tasks_display(self):
        """
        Display buildings' tasks based on the loaded data and settings.
        """
        data = self.load_data()
        settings = self.load_settings()

        # Clear existing widgets in frame_buildings_tasks
        for widget in self.frame_buildings_tasks.winfo_children():
            widget.destroy()

        # Now recreate the widgets based on the current data
        for i, (task_id, task_info) in enumerate(data["buildings"].items(), start=1):
            self.frame_buildings_tasks.rowconfigure(i, weight=1)

            planet_name = task_info["planet"]
            planet = self.convert_to_snake_case(planet_name)
            image_planet = ctk.CTkImage(
                Image.open(
                    Path(
                        PLANETS_IMAGES_PATH,
                        settings["planets_settings"][planet]["planet_image"],
                    ),
                ),
                size=(40, 40),
            )
            label_planet = ctk.CTkLabel(
                self.frame_buildings_tasks,
                text=f" {planet_name}",
                font=("Arial", 16),
                image=image_planet,
                compound="left",
            )
            label_planet.grid(row=i, column=1)

            building = task_info["building"]
            building_image_name = building.replace(" ", "_")
            building_image = f"{building_image_name}.png"
            image_building = ctk.CTkImage(
                Image.open(Path(MAIN_IMAGES_PATH, building_image)), size=(40, 40)
            )

            label_image_building = ctk.CTkLabel(
                self.frame_buildings_tasks,
                text=f" {building}",
                font=("Arial", 16),
                image=image_building,
                compound="left",
            )
            label_image_building.grid(row=i, column=2)

            label_cooldown = ctk.CTkLabel(
                self.frame_buildings_tasks,
                text=self.set_buildings_cooldown_text(task_id),
                font=("Arial", 16),
            )
            label_cooldown.grid(row=i, column=3)

            image_trashcan = ctk.CTkImage(
                Image.open(Path(MAIN_IMAGES_PATH, "dark_mode_trash_can.png")),
                size=(20, 20),
            )

            button_remove_task = ctk.CTkButton(
                self.frame_buildings_tasks,
                text="",
                fg_color="red",
                hover_color="dark red",
                width=30,
                image=image_trashcan,
                command=lambda task_id=task_id: self.remove_buildings_task(task_id),
            )
            button_remove_task.grid(row=i, column=4)

    def set_buildings_cooldown_text(self, task_id: str) -> str:
        data = self.load_data()

        cooldown_date = data["buildings"][task_id]["cooldown"]

        if self.compare_to_current_time(cooldown_date):
            if "refinery" in task_id:
                return "Cube Refined!"
            else:
                return "Upgrade Finished!"
        else:
            cooldown_date_datetime = datetime.fromisoformat(cooldown_date)
            return f"Ready on {cooldown_date_datetime: %d-%m-%Y %H:%M}"

    @staticmethod
    def load_data() -> dict:
        """
        Loads the data from data.json

        :return: dictionary with all the data from data.json
        """
        json_data_file = Path(MAIN_PATH, "data.json")
        with open(json_data_file, "r") as file:
            data = json.load(file)
        return data

    @staticmethod
    def save_data(data: dict):
        """
        Saves the data to data.json

        :param data: dictionary with data from data.json
        """
        json_data_file = Path(MAIN_PATH, "data.json")
        with open(json_data_file, "w") as file:
            json.dump(data, file, indent=4)

    @staticmethod
    def load_settings() -> dict:
        """
        Loads the settings from settings.json

        :return: dictionary with all the settings from settings.json
        """

        json_settings_file = Path(MAIN_PATH, "settings.json")
        with open(json_settings_file, "r") as file:
            settings = json.load(file)
        return settings

    @staticmethod
    def save_settings(settings: dict):
        """
        Save the provided settings to the specified JSON settings file.

        :param settings: A dictionary containing the settings to be saved.
        """

        json_settings_file = Path(MAIN_PATH, "settings.json")
        with open(json_settings_file, "w") as file:
            json.dump(settings, file, indent=4)

    @staticmethod
    def compare_to_current_time(cooldown_date: str) -> bool:
        """
        Compares the current time to the provided cooldown_date datetime

        :param cooldown_date: The datetime to compare to the current time, must be in ISO 8601 format (datetime.isoformat())
        :return: True if the current datetime is later or equal to the provided cooldown date, False if the current datetime is earlier than the provided cooldown date
        """

        current_datetime = datetime.now()

        try:
            cooldown_datetime = datetime.fromisoformat(cooldown_date)
        except:
            raise ValueError(
                "Invalid datetime format. Please format the datetime to isoformat"
            )

        return current_datetime >= cooldown_datetime

    @staticmethod
    def toggle_command_window(action: str) -> None:
        """
         Toggles the command window visibility based on the action parameter.

        :param action: "show" to show the command window, "hide" to hide it.
        """
        whnd = ctypes.windll.kernel32.GetConsoleWindow()
        if whnd != 0:
            if action.lower() == "hide":
                ctypes.windll.user32.ShowWindow(whnd, 0)  # 0 = SW_HIDE
            elif action.lower() == "show":
                ctypes.windll.user32.ShowWindow(whnd, 1)  # 1 = SW_SHOWNORMAL
            else:
                raise ValueError("Invalid action. Use 'show' or 'hide'")

    @staticmethod
    def background_command_window() -> None:
        """Keeps the command window running in the background for sending notifications"""
        whnd = ctypes.windll.kernel32.GetConsoleWindow()
        if whnd != 0:
            ctypes.windll.user32.ShowWindow(whnd, 0)
            ctypes.windll.kernel32.CloseHandle(whnd)

    def on_closing(self) -> None:
        """Closes the window and reindexes the task ids from workers and buildings. If enabled in the settings, it will also delete expired tasks"""
        print("Closing window")

        data = self.load_data()
        settings = self.load_settings()

        # Remove expired workers tasks if enabled in the settings
        if settings["global_settings"]["auto_delete_completed_tasks"]:
            keys_to_delete = []
            for section in ["workers", "buildings"]:
                for task_id, task_info in data[section].items():
                    if task_info["cooldown_finished"]:
                        keys_to_delete.append((section, task_id))

            # Delete the expired tasks
            for section, task_id in keys_to_delete:
                del data[section][task_id]

        # Reindex the task ids
        for section in ["workers", "buildings"]:
            new_section = {}
            counter = {}
            for task_id, task_info in data[section].items():
                parts = task_id.rsplit("_", 1)
                base = "_".join(parts[:-1])
                if base not in counter:
                    counter[base] = 1
                else:
                    counter[base] += 1
                new_task_id = f"{base}_{counter[base]}"
                new_section[new_task_id] = task_info
            data[section] = new_section

        self.save_data(data)

        if settings["global_settings"]["run_notifications_in_background"]:
            self.background_command_window()
        else:
            os.remove(LOCK_FILE_PATH)

        self.destroy()


def create_data_json():
    print("Creating data.json")

    default_data_json_template = {
        "star_battery": {"cooldown": "", "cooldown_finished": False},
        "tool_case": {"cooldown": "", "cooldown_finished": False},
        "helmet": {"cooldown": "", "cooldown_finished": False},
        "workers": {},
        "buildings": {},
    }
    with open("data.json", "w") as file:
        json.dump(default_data_json_template, file, indent=4)


def create_settings_json():
    print("Creating settings.json")

    default_settings_json_template = {
        "global_settings": {
            "star_battery": True,
            "tool_case": True,
            "helmet": True,
            "workers": True,
            "buildings": True,
            "auto_delete_completed_tasks": False,
            "check_checkbox_instant_build_time_on_startup": False,
            "disable_notifications_during_startup": True,
            "run_notifications_in_background": True,
            "show_command_window": False,
        },
        "planets_settings": {
            "main_planet": {"enabled": True, "planet_image": "Planet_main.png"},
            "colony_1": {"enabled": False, "planet_image": ""},
            "colony_2": {"enabled": False, "planet_image": ""},
            "colony_3": {"enabled": False, "planet_image": ""},
            "colony_4": {"enabled": False, "planet_image": ""},
            "colony_5": {"enabled": False, "planet_image": ""},
            "colony_6": {"enabled": False, "planet_image": ""},
            "colony_7": {"enabled": False, "planet_image": ""},
            "colony_8": {"enabled": False, "planet_image": ""},
            "colony_9": {"enabled": False, "planet_image": ""},
            "colony_10": {"enabled": False, "planet_image": ""},
            "colony_11": {"enabled": False, "planet_image": ""},
        },
    }
    with open("settings.json", "w") as file:
        json.dump(default_settings_json_template, file, indent=4)


if __name__ == "__main__":
    # Check if data.json exists
    if not os.path.exists("data.json"):
        create_data_json()

    # Check if settings.json exists
    if not os.path.exists("settings.json"):
        create_settings_json()

    # Start the GUI
    main_window = MainWindow()
    main_window.protocol("WM_DELETE_WINDOW", main_window.on_closing)
    main_window.mainloop()
