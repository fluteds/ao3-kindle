import logging
import os
import re
import requests
import smtplib
import hashlib
import subprocess
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from urllib import parse as urlparse
from getpass import getpass
from configparser import ConfigParser
from argparse import ArgumentParser
from appdirs import user_data_dir
from bs4 import BeautifulSoup
from PIL import Image, ImageDraw, ImageFont

# TODO Add metadata to the files in a way that Amazon doesn't reject the file
# TODO Add custom covers and text to files for .epub extensions

def get_ebook(src_url: str, format: str = "epub") -> str:
    logging.debug("URL Passed: %s" % src_url)
    logging.debug("File format: %s" % format)

    # Parse the AO3 work URL to get work ID
    src_url_split = urlparse.urlparse(src_url).path.split("/")
    workid = src_url_split[src_url_split.index("works") + 1]

    # Fetch the work details
    work_url = f"https://archiveofourown.org/works/{workid}"
    logging.info(f"Fetching AO3 work details for work ID: {workid}")
    response = requests.get(work_url)
    soup = BeautifulSoup(response.content, 'html.parser')

    title = soup.find('h2', {'class': 'title'}).text.strip()
    # Clean up the title for filename
    title = re.sub(r"[^\w\s-]", "", title)  # Remove unwanted characters
    title = re.sub(r"\s+", " ", title)  # Replace multiple spaces with a single space
    title = title.title()  # Convert to proper case

    # Ensure the output directory exists
    output_dir = os.path.join(os.getcwd(), "output")
    os.makedirs(output_dir, exist_ok=True)

    # Construct file path in the output directory
    file_path = os.path.join(output_dir, f"{title}.{format}")
    
    # Construct download URL
    dl_url = f"https://archiveofourown.org/downloads/{workid}/{title}.{format}"
    logging.info('Downloading from URL: "%s"' % dl_url)

    response = requests.get(dl_url)
    with open(file_path, 'wb') as file:
        file.write(response.content)

    logging.info(f"Downloaded {file_path} from AO3.")
    return file_path

def send_to_kindle(file_path: str, kindle_email: str, smtp_server: str, smtp_sender: str, smtp_password: str) -> None:
    msg = MIMEMultipart()
    msg['From'] = smtp_sender
    msg['To'] = kindle_email
    msg['Subject'] = 'Convert Kindle Document'

    with open(file_path, 'rb') as file:
        part = MIMEBase('application', 'octet-stream')
        part.set_payload(file.read())
        encoders.encode_base64(part)
        part.add_header('Content-Disposition', f'attachment; filename={os.path.basename(file_path)}')
        msg.attach(part)

    try:
        with smtplib.SMTP(smtp_server, 587) as server:
            server.starttls()
            server.login(smtp_sender, smtp_password)
            server.send_message(msg)
            logging.info(f"Successfully sent {file_path} to {kindle_email}")
    except Exception as e:
        logging.error(f"Failed to send email: {e}")
        raise

def hash_file(file_path: str) -> str:
    """Compute the SHA256 hash of the file content."""
    sha256 = hashlib.sha256()
    with open(file_path, 'rb') as file:
        while chunk := file.read(8192):
            sha256.update(chunk)
    return sha256.hexdigest()

def load_processed_urls(record_file: str) -> dict:
    """Load the set of processed URLs and their hashes from a record file."""
    if os.path.exists(record_file):
        with open(record_file, 'r') as file:
            return dict(line.strip().split('\t', 1) for line in file)
    return {}

def save_processed_url(record_file: str, url: str, file_hash: str) -> None:
    """Append a processed URL and its file hash to the record file."""
    with open(record_file, 'a') as file:
        file.write(f"{url}\t{file_hash}\n")

def update_cover_with_title(ebook_path: str, cover_path: str) -> None:
    with Image.open(cover_path) as cover_image:
        draw = ImageDraw.Draw(cover_image)
        font = ImageFont.load_default()
        
        title = os.path.splitext(os.path.basename(ebook_path))[0]
        
        # Calculate text size and position using textbbox
        text_bbox = draw.textbbox((0, 0), title, font=font)
        text_width = text_bbox[2] - text_bbox[0]
        text_height = text_bbox[3] - text_bbox[1]
        
        image_width, image_height = cover_image.size
        text_x = (image_width - text_width) / 2
        text_y = image_height - text_height - 10
        
        # Add title to the cover
        draw.text((text_x, text_y), title, font=font, fill="white")
        
        # Save the modified cover image
        cover_with_title_path = os.path.join(
            os.path.dirname(ebook_path),
            f"cover_{os.path.basename(ebook_path)}"
        )
        cover_image.save(cover_with_title_path)

    logging.info(f"Updated cover with title saved at {cover_with_title_path}")

    # Update ebook with new cover
    temp_path = ebook_path + ".temp"
    try:
        subprocess.run([
            'ebook-convert', ebook_path, temp_path,
            '--cover', cover_with_title_path
        ], check=True)
        
        # Replace original ebook with the updated one
        os.rename(temp_path, ebook_path)
        logging.info(f"Cover updated for {ebook_path}")
    except subprocess.CalledProcessError as e:
        logging.error(f"Error adding cover: {e}")
        raise

def generate_config(dest: str) -> None:
    print("Regenerating Configuration...")
    config = ConfigParser()
    config["DEFAULT"] = {}
    out_dict = config["DEFAULT"]

    while True:
        print("Email Address for Send-to-Kindle: ", end="")
        out_dict["kindle"] = input()

        print("SMTP Server to send from: ", end="")
        out_dict["smtp-server"] = input()

        print("SMTP sender email: ", end="")
        out_dict["smtp-sender"] = input()

        print("Store a password? Useful for ex. gmail app-specific passwords")
        print(
            "(WARNING: will be stored as plaintext,"
            + " not recommended for general passwords)"
        )
        print("(y/n): ", end="")
        if input().lower().strip()[:1] == "y":
            print("SMTP Password: ", end="")
            out_dict["smtp-password"] = input()

        print("Is this correct?")
        print("Kindle email: %s" % out_dict["kindle"])
        print(
            "  SMTP: %s on %s"
            % (out_dict["smtp-server"], out_dict["smtp-sender"])
        )
        print("(y/n): ", end="")
        if input().lower().strip()[:1] == "y":
            break

    logging.debug("Writing config file to %s" % dest)
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    with open(dest, "w") as cfgfile:
        config.write(cfgfile)
    logging.debug("Write complete")

def read_config(dest: str) -> dict:
    cfgfile = ConfigParser()
    logging.debug("Reading config file from %s" % dest)
    cfgfile.read(dest)
    logging.debug("Read complete")
    return cfgfile["DEFAULT"]

def process_urls(urls: list, cfg: dict, cover_path: str) -> None:
    logging.info(f"Processing {len(urls)} URLs")

    record_file = os.path.join(os.getcwd(), 'processed_urls.txt')
    processed_urls = load_processed_urls(record_file)

    if "smtp-password" in cfg:
        p = cfg["smtp-password"]
    else:
        p = getpass('Password for "%s": ' % cfg["smtp-sender"])

    for idx, url in enumerate(urls, start=1):
        try:
            logging.info(f"Processing {idx}/{len(urls)}: {url}")

            # Fetch the work details and construct file path
            file_path = get_ebook(url)

            # Compute the hash of the file
            file_hash = hash_file(file_path)

            # Check if the URL has been processed and if the file has changed
            if url in processed_urls:
                last_hash = processed_urls[url]
                if file_hash == last_hash:
                    logging.info(f"Skipping URL as it has not been updated: {url}")
                    continue

            if cover_path:
                update_cover_with_title(file_path, cover_path)

            send_to_kindle(
                file_path=file_path,
                kindle_email=cfg["kindle"],
                smtp_server=cfg["smtp-server"],
                smtp_sender=cfg["smtp-sender"],
                smtp_password=p,
            )
            
            save_processed_url(record_file, url, file_hash)
            logging.info(f"Successfully processed {url}")
        except Exception as e:
            logging.error(f"Error processing {url}: {e}")

    logging.info("All URLs processed successfully.")

def main() -> None:
    cfgfile_default = os.path.join(
        user_data_dir(appname="ao3-kindle", appauthor=False, roaming=True),
        "conf",
    )

    cli = ArgumentParser(
        description="AO3 to Kindle: Download AO3 works and send them to your Kindle."
    )
    cli.add_argument(
        "urls_file",
        type=str,
        help="Path to a text file containing the AO3 work URLs."
    )
    cli.add_argument(
        "--cover",
        type=str,
        default="",
        help="Path to a custom cover image. If not provided, default cover is used."
    )
    cli.add_argument(
        "--config",
        type=str,
        default=cfgfile_default,
        help="Path to the configuration file."
    )

    args = cli.parse_args()
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    # Check if config exists
    if not os.path.exists(args.config):
        generate_config(args.config)

    # Read configuration
    cfg = read_config(args.config)

    # Read URLs from file
    with open(args.urls_file, 'r') as file:
        urls = [line.strip() for line in file if line.strip()]

    process_urls(urls, cfg, args.cover)

if __name__ == "__main__":
    main()
