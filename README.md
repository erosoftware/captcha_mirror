Captcha Mirror

SICAR Shapefile Download Assistant

Captcha Mirror is a lightweight utility that simplifies the process of accessing and downloading shapefiles from Brazil’s SICAR system. It works as a bridge between your application and SICAR, handling technical complexities while ensuring full compliance — CAPTCHAs are always solved by real users, not bots.


---

Why Use Captcha Mirror?

Automates part of the SICAR shapefile download workflow

Provides a clean, reusable interface for integration with other tools (like Erθ View)

Maintains ethical and legal standards by requiring human CAPTCHA solving

Speeds up repetitive tasks while giving developers flexibility and control



---

Features

Request shapefile downloads from SICAR with minimal effort

Use in standalone mode or integrate with other apps

Human-in-the-loop CAPTCHA handling

Easily extendable for other geographic data workflows



---

Requirements

Python 3.6+

Required libraries listed in requirements.txt

Chrome or Chromium-based browser

Internet connection



---

Installation

git clone https://github.com/your-user/captcha-mirror.git
cd captcha-mirror
pip install -r requirements.txt


---

Usage

python captcha_mirror.py

When prompted, solve the CAPTCHA manually in the opened browser window. The system will then proceed to download the requested shapefiles.


---

Use Cases

As a companion tool to Erθ View

For researchers or developers working with Brazilian rural property data

As a standalone utility in GIS pipelines



---

Project Status & Roadmap

[x] Manual CAPTCHA resolution

[x] SICAR download automation

[ ] CLI enhancements

[ ] Browser automation improvements

[ ] Logging and error handling upgrades



---

Contributing

This project welcomes contributions!

Fork the repository

Create a feature branch

Submit a pull request with your changes


Let’s build a more efficient, transparent way to access rural environmental data.


---

License

Licensed under the Apache License 2.0.