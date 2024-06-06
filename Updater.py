import os
import time

import psutil
import requests

# TODO: Add code which always converts the old settings file with the new settings file using templates and filling it in with the settings it currently has


def get_current_version():
    try:
        with open("version.txt", "r") as file:
            return file.read().strip()
    except FileNotFoundError:
        return None

def get_latest_version(repo_url):
    response = requests.get(repo_url + "version.txt")
    if response.status_code == 200:
        return response.text.strip()
    else:
        return None

def download_new_version(repo_url, filename):
    response = requests.get(repo_url + filename, allow_redirects=True)
    if response.status_code == 200:
        with open(filename, "wb") as file:
            file.write(response.content)
        return True
    return False


def kill_process(process_name):
    """Kill all processes with the given name."""
    for proc in psutil.process_iter(["pid", "name"]):
        if proc.info["name"] == process_name:
            proc.kill()


def main():
    repo_url = (
        "https://raw.githubusercontent.com/0DarkPhoenix/Galaxy-Life-Notifier/v1.2/"
    )

    current_version = get_current_version()
    latest_version = get_latest_version(repo_url)

    if current_version is None or latest_version is None:
        print("Failed to retrieve versions.")
        return

    print(f"Current version: {current_version}")
    print(f"Latest version: {latest_version}")

    if latest_version > current_version:
        print(
            "New version available! Please close the application to proceed with the update."
        )
        input("Press ENTER after you have closed the application.")

        exe_filename = "Galaxy Life Notifier.exe"
        process_name = "Galaxy Life Notifier.exe"  # The name of the process to kill

        # Optionally kill the process automatically
        kill_process(process_name)

        if download_new_version(repo_url, exe_filename):
            with open("version.txt", "w") as file:
                file.write(latest_version)
            print("Update successful. Please restart the application.")
        else:
            print("Failed to download the new version.")
    else:
        print("You are up-to-date!")

if __name__ == "__main__":
    main()
