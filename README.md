# NotifyPlex
Refreshes Plex library after successful NZBGet download and optionally sends GUI notification to Plex Home Theater

## Requirements

This post-processing script requires python3 and the 'requests' module to be installed on your system

**NOTE:** To install 'requests' module, do `pip install requests`

## Features

* Detects NZBGet category and performs targeted refresh on Movie or TV libraries

* Optionally refreshes custom section numbers as defined in settings

* Optionally sends GUI notification to Plex Home Theater

* Works with Plex Home by authenticating with plex.tv

* Stores auth_token to disk after initial sign-in

* Useful for libraries stored on NAS shares where PMS cannot detect changes

## Installation 

* Clone repository into your NZBGet scripts directory

`git clone https://github.com/mannibis/NotifyPlex.git`

* Make script executable

`chmod +x NotifyPlex.py`

* Configure variables within NZBGet Web UI

**NOTE:** Plex Username and Password are only required to fetch auth token, which will be stored inside your NotifyPlex folder and subsequently re-used
