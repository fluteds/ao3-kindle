# AO3 to Kindle

This script allows you to download fanfiction works from Archive of Our Own (AO3) and send them directly to your Amazon Kindle device via email.

## Features

- Download AO3 works in EPUB format.
- Send downloaded works to Kindle via email.
- Easy configuration for SMTP settings and Kindle email address.
- Uses file hashes to determine if a fic has been updated.

## Installation

1. Clone the repository
2. Install required Python packages:

    ```bash
    pip install -r requirements.txt
    ```

## Usage

1. Configure the script:

    Run the following command to generate the configuration file:

    ```bash
    python main.py --configure
    ```

    Follow the prompts to enter your Kindle email address and SMTP server settings.

2. Run the script:

    To process a single AO3 URL:

    ```bash
    python main.py https://archiveofourown.org/works/12345678
    ```

    To process a list of URLs from a file:

    ```bash
    python main.py urls.txt
    ```

    The file `urls.txt` should contain one AO3 URL per line.

## Configuration

The script will create a configuration file at `~/.config/ao3-kindle/conf` (on Unix-based systems) or `C:\Users\<YourUsername>\AppData\Roaming\ao3-kindle\conf` (on Windows) where your SMTP server and Kindle email settings will be saved.

## Notes

- Ensure that your Kindle email address is added to your Amazon account's approved email list.
- Make sure that your SMTP server settings are correct, and that you use an app-specific password if your email provider requires it.
