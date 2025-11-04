Description
The SICAR CAPTCHA Mirror is a user-friendly interface for downloading shapefiles from the Brazilian Rural Environmental Registry System (SICAR). The tool acts as a bridge between the user and the SICAR website, simplifying the CAPTCHA-solving and file download process.

Features
User-friendly web interface for interacting with the SICAR website

Automatic CAPTCHA detection on the page

Display of the CAPTCHA for manual user input

Simplified download management

Detailed logs for debugging

How It Works
The application opens an automated session on the SICAR website

The user navigates normally through the site to find the desired property

When a CAPTCHA is found, the image is extracted and displayed in the interface

The user (human) types the CAPTCHA characters

The application sends the characters to the SICAR website

The shapefile download starts automatically

Challenges and Known Limitations
CAPTCHA Detection
One of the main limitations is reliably detecting the CAPTCHA on the SICAR website.
The system implements multiple strategies to identify the CAPTCHA:

Direct search for <img> elements containing “captcha” in the URL

Search for text elements related to CAPTCHA

Search for input fields with the name/ID “captcha”

Search for text containing “code” or “código”

Analysis of iframes for possible CAPTCHAs

Even with these strategies, some CAPTCHAs may not be detected automatically due to changes in the website’s structure or dynamically loaded elements.

Compliance and Ethics
This software does NOT violate the CAPTCHA protection of the SICAR website, because:

It does not perform any kind of automated character recognition

All CAPTCHAs are solved manually by humans

The tool only facilitates CAPTCHA viewing and input

The user is responsible for correctly identifying and typing the characters

The tool acts solely as a facilitating interface and does not attempt to bypass or automate CAPTCHA resolution, thereby respecting the security mechanism’s intended purpose.

Requirements
Python 3.7+

Flask

Flask-SocketIO

Selenium

Chrome WebDriver

Installation
Clone this repository

Install dependencies: pip install -r requirements.txt

Run the script: python captcha_mirror.py

Usage
Access http://localhost:5001 in your browser

Click on “Start Browser”

Navigate to the desired property on the SICAR website

When a CAPTCHA appears, it will be displayed in the interface (or click “Force Shapefile Download”)

Enter the CAPTCHA characters and click “Submit CAPTCHA”

The shapefile download will start automatically

Support
This tool was developed to facilitate access to public data available on SICAR.