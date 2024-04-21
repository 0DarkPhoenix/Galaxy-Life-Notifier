import threading
import time

import schedule


def print_finished():
    print("Finished")


def wait_or_advance():
    # This function waits for Enter or a timeout
    input("Press Enter to advance immediately or wait 10 seconds...")


def scheduled_job():
    # Schedule the print_finished function every 10 seconds
    schedule.every(10).seconds.do(print_finished)

    while True:
        # Run all scheduled tasks
        schedule.run_pending()
        time.sleep(1)  # Sleep to prevent high CPU usage


def main():
    # Start the scheduled job in a separate thread
    thread = threading.Thread(target=scheduled_job)
    thread.start()

    while True:
        # Wait for user input or timeout
        timer = threading.Timer(10, lambda: None)  # Dummy function after timeout
        timer.start()
        wait_or_advance()
        timer.cancel()  # Cancel the timer if input is received before timeout

        # Clear all scheduled jobs and reschedule
        schedule.clear()
        scheduled_job()


if __name__ == "__main__":
    main()
