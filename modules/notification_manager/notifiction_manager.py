class NotificationManager:
    def __init__(self):
        self.running = True

    async def notification_checker(self) -> None:
        """Check the data.json file for scheduled notifications and sends notifications if needed."""
        settings = MainWindow.load_settings()
        self.global_settings = settings["global_settings"]
        self.first_iteration = settings["global_settings"]["disable_notifications_during_startup"]

        while self.running:
            self.data = MainWindow.load_data()
            min_cooldown_time = None
            run_workers_task_display = False
            run_buildings_task_display = False

            min_cooldown_time = await self.process_items(min_cooldown_time)
            (
                run_workers_task_display,
                run_buildings_task_display,
                min_cooldown_time,
            ) = await self.process_tasks(min_cooldown_time)

            await self.update_displays(run_workers_task_display, run_buildings_task_display)

            if self.first_iteration:
                self.first_iteration = False

            sleep_duration = self.calculate_sleep_duration(min_cooldown_time)

            print(f"Sleeping for {sleep_duration} seconds...")
            await asyncio.sleep(sleep_duration)

    async def process_items(self, min_cooldown_time):
        for item in [ItemsEnum.star_battery, ItemsEnum.tool_case, ItemsEnum.helmet]:
            if not self.data[item]["cooldown_finished"]:
                scheduled_time = self.data[item]["cooldown"]
                if MainWindow.compare_to_current_time(scheduled_time):
                    MainWindow.set_item_text(main_window, item)
                    self.cooldown_finished(item=item)
                    self.process_notification(item=item)
                min_cooldown_time = self.update_min_cooldown_time(min_cooldown_time, scheduled_time)
        return min_cooldown_time

    async def process_tasks(self, min_cooldown_time):
        run_workers_task_display = False
        run_buildings_task_display = False
        for section in ["workers", "buildings"]:
            for task_id, task_info in self.data[section].items():
                if not task_info["cooldown_finished"]:
                    scheduled_time = task_info["cooldown"]
                    if MainWindow.compare_to_current_time(scheduled_time):
                        self.cooldown_finished(section=section, task_id=task_id)
                        self.process_notification(section=section, task_info=task_info)
                        if section == "workers":
                            run_workers_task_display = True
                        elif section == "buildings":
                            run_buildings_task_display = True
                    min_cooldown_time = self.update_min_cooldown_time(
                        min_cooldown_time, scheduled_time
                    )
        return run_workers_task_display, run_buildings_task_display, min_cooldown_time

    async def update_displays(self, run_workers_task_display, run_buildings_task_display):
        if run_workers_task_display:
            MainWindow.workers_tasks_display(main_window)
        if run_buildings_task_display:
            MainWindow.buildings_tasks_display(main_window)

    def calculate_sleep_duration(self, min_cooldown_time):
        if min_cooldown_time:
            sleep_duration = ceil(max((min_cooldown_time - datetime.now()).total_seconds(), 1))
            sleep_duration = min(sleep_duration, 60)
        else:
            sleep_duration = 60
        return sleep_duration

    def process_notification(
        self,
        *,
        item: ItemsEnum = None,
        section: str | None = None,
        task_info: str | None = None,
    ) -> None:
        """
        Check if the notification is send before and sends it if the previous is false.

        :param item: The item to check (e.g. "star_battery", "tool_case", "helmet")
        :param section: The section of the task to check (e.g. "workers", "buildings")
        :param task_info: The information of a task_id
        """
        global_settings = self.global_settings

        # Check if it's the first iteration and notifications should be disabled
        if self.first_iteration and global_settings["disable_notifications_during_startup"]:
            return

        def determine_message(
            item: ItemsEnum | None,
            section: str | None,
            planet: str,
            building: str | None,
        ) -> str:
            """
            Determine which message needs to be send in the notification.

            :param item: An item(e.g. "star_battery", "tool_case", "helmet")
            :param section: The section of the task (e.g. "workers", "buildings")
            :param task_info: The information of a task_id

            :return: The message to send in the notification
            """
            special_npc = None
            message_firebit = None
            message_elderby = None

            if item is not None and global_settings[item]:
                message = f"You can collect your {item.replace('_', ' ').title()} again!"

            if section is not None and global_settings[section]:
                if global_settings["unique_messages"]:
                    match section:
                        case "workers":
                            messages = {
                                f"I'm finished on {planet}, Chief!": None,
                                f"I'm done. Check out my beautiful work on {planet}!": None,
                                f"I'm finished on {planet}, I hope you like it!": None,
                                f"I'm done, {planet} looks even better now!": None,
                                f"I've completed my task on {planet}, Chief!": None,
                                f"I finished my task on {planet}. I'm ready for the next one!": None,
                                f"I've worked tirelessly on {planet}, Chief. I don't need any sleep!": None,
                                f"I worked for so long on {planet}, I wonder how I'm still not buffed!": None,
                            }
                            if global_settings["unique_icons"]:
                                message_firebit = f"I see your worker has finished upgrading on {planet}. I can't wait to see my army lay that building in ruin!"
                                message_elderby = f"Your worker on {planet} is done, young Starling. Your base has matured greatly since I've last seen it!"
                                messages.update(
                                    {
                                        message_firebit: 0.01,
                                        message_elderby: 0.01,
                                    }
                                )

                        case "buildings":
                            match building:
                                case "Laboratory":
                                    messages = {
                                        f"Your upgraded unit on {planet} is done!": None,
                                        f"I've finished upgrading your unit on {planet}, Chief!": None,
                                        f"I've made a unit on {planet} even stronger, and you can use him now!": None,
                                    }
                                    if global_settings["unique_icons"]:
                                        message_firebit = f"I see you upgraded a unit on {planet}. Don't be happy about it, you still won't stand a chance against me!"
                                        message_elderby = f"Your unit on {planet} has been upgraded, young Starling. He looks even more powerful than before!"
                                        messages.update(
                                            {
                                                message_firebit: 0.02,
                                                message_elderby: 0.02,
                                            }
                                        )

                                case "Refinery":
                                    messages = {
                                        "Your cube is refined, Chief!": None,
                                        "I've refined your cube, I wonder what's inside!": None,
                                        "Another refined cube is ready, Chief!": None,
                                    }

                                case _:
                                    messages = {
                                        f"Your units from the {building} on {planet} are ready!": None,
                                        f"Your units from the {building} on {planet} are ready to strike on your command!": None,
                                        f"All units from the {building} on {planet} are trained. Lets show everyone who's the best in the galaxy!": None,
                                        f"All units from the {building} on {planet} are ready to teach someone a lesson!": None,
                                    }

                    message = randomly_choose_option(messages)

                    if message == message_firebit:
                        special_npc = "Firebit"
                    elif message == message_elderby:
                        special_npc = "Elderby"

                else:
                    # Default message for workers and buildings if unique_messages is not enabled
                    message = f"Your {building if section == 'buildings' else 'Worker'} on {planet} is done!"

            return message, special_npc

        def determine_icon(
            item: ItemsEnum | None,
            section: str | None,
            building: str,
            special_npc: str | None = None,
        ) -> str:
            """
            Determine the icon to be displayed in the notification.

            :param item: An item (e.g. "star_battery", "tool_case", "helmet")
            :param section: The section of the task (e.g. "workers", "buildings")
            :param building: The name of the building
            :param special_npc: The name of the special NPC when a special message will be displayed (e.g. "Firebit", "Elderby")

            :return: The file name of the icon to be displayed in the notification
            """
            icon_images = None

            if global_settings["unique_icons"]:
                if item:
                    icon_images = {
                        "Chubi.ico": None,
                        "Chubi_Happy.ico": None,
                    }

                match section:
                    case "workers":
                        icon_images = {
                            "Worker.ico": None,
                            "Worker_Happy.ico": None,
                        }
                    case "buildings":
                        if building == "Laboratory" or building == "Refinery":
                            icon_images = {
                                "Chubi.ico": None,
                                "Chubi_Happy.ico": None,
                            }
                        elif building in ["Training Camp", "Factory", "StarPort"]:
                            icon_images = {
                                "Major_Wor.ico": None,
                                "Major_Wor_Happy.ico": None,
                            }
                if icon_images:
                    icon_image = randomly_choose_option(icon_images)

                match special_npc:
                    case "Firebit":
                        icon_image = "Firebit.ico"
                    case "Elderby":
                        icon_image = "Elderby.ico"
            else:
                icon_image = "Starling_Postman_AI_Upscaled.ico"

            return icon_image

        def randomly_choose_option(options: dict[str, float | None]) -> str:
            """
            Randomly chooses an option. Probabilities get automatically calculated.

            :param options: The list of options. An option can be passed with a custom probability of type float. If you don't want a custom probability for that option, pass None
            :return: The chosen option
            """
            total_specified_probability = sum(
                probability for probability in options.values() if probability is not None
            )
            unspecified_options = [
                msg for msg, probability in options.items() if probability is None
            ]
            num_unspecified = len(unspecified_options)
            if num_unspecified > 0:
                regular_probability = (1.0 - total_specified_probability) / num_unspecified
                for msg in unspecified_options:
                    options[msg] = regular_probability

            options, probabilities = zip(*options.items())
            return random.choices(options, probabilities)[0]

        # Main process_notification logic
        if item is not None or section is not None and task_info is not None:
            planet = None
            building = None

            if task_info is not None:
                planet = (
                    "your Main Planet"
                    if task_info["planet"] == "Main Planet"
                    else task_info["planet"]
                )
                building = task_info["building"] if section == "buildings" else None

            message, special_npc = determine_message(item, section, planet, building)
            icon = determine_icon(item, section, building, special_npc)
            self.send_notification(message, icon)

    def send_notification(self, message: str, icon_image: str) -> None:
        """
        Send the notification using winotify.

        :param message: The message to be displayed in the notification
        :param icon_image: The icon to be displayed in the notification
        """
        title = "Galaxy Life Notifier"
        icon_path = str(Path(MAIN_IMAGES_PATH, icon_image))

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

    def update_min_cooldown_time(self, current_min: datetime | None, new_time: str) -> datetime:
        new_time_datetime = datetime.fromisoformat(new_time)
        if new_time_datetime and (current_min is None or new_time_datetime < current_min):
            return new_time_datetime
        return current_min

    def cooldown_finished(
        self,
        *,
        item: ItemsEnum | None = None,
        section: str | None = None,
        task_id: str | None = None,
    ) -> None:
        """
        Change the cooldown_finished parameter to true in data.json for the given section and task_id.

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

    def run(self) -> None:
        """Run the notification checker."""
        self.check_and_handle_existing_instance()
        self.create_lock_file()
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self.notification_checker())
        finally:
            self.cleanup()

    def check_and_handle_existing_instance(self) -> None:
        """Check if an instance of the notification manager is already running and kills it if it is."""
        if os.path.exists(LOCK_FILE_PATH):
            try:
                with open(LOCK_FILE_PATH, "r") as file:
                    old_pid = int(file.read().strip())
                if self.is_process_running(old_pid):
                    self.terminate_process(old_pid)
                else:
                    print(f"No existing process with PID {old_pid} found.")
            except ValueError:
                print(
                    "Lock file does not contain a valid PID. It may be corrupted or manually edited."
                )
            except Exception as e:
                print(f"An error occurred while handling the lock file: {e}")

    def is_process_running(self, pid):
        """Check if a process with the given PID is still running."""
        try:
            p = psutil.Process(pid)
            return p.is_running()
        except psutil.NoSuchProcess:
            return False

    def terminate_process(self, pid):
        """Terminate the process with the given PID."""
        try:
            p = psutil.Process(pid)
            p.terminate()  # Sends a SIGTERM
            p.wait()  # Wait for the process to terminate
            print(f"Successfully terminated the process with PID {pid}.")
        except psutil.NoSuchProcess:
            print(f"No process found with PID {pid}.")
        except psutil.AccessDenied:
            print(f"Access denied when trying to terminate the process with PID {pid}.")
        except Exception as e:
            print(f"Failed to terminate the process with PID {pid}: {e}")

    def create_lock_file(self) -> None:
        """Create a lock file to prevent multiple instances of the notification manager from running."""
        with open(LOCK_FILE_PATH, "w") as lock_file:
            lock_file.write(str(os.getpid()))  # Write the current PID

    def cleanup(self) -> None:
        """Clean up the lock file and sets the self.running flag to False."""
        if os.path.exists(LOCK_FILE_PATH):
            os.remove(LOCK_FILE_PATH)
        self.running = False
