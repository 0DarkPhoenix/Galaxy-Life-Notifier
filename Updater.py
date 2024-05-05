import os

import requests


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


def main():
    # GitHub repository URL where the exe and version.txt are stored
    repo_url = "https://raw.githubusercontent.com/0DarkPhoenix/Galaxy-Life-Notifier/v1.2/version.txt"

    current_version = get_current_version()
    latest_version = get_latest_version(repo_url)

    if current_version is None or latest_version is None:
        print("Failed to retrieve versions.")
        return

    print(f"Current version: {current_version}")
    print(f"Latest version: {latest_version}")

    if latest_version > current_version:
        print("New version available! Downloading...")
        exe_filename = "your_program.exe"
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
