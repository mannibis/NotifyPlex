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

* Stores auth token to disk after initial sign-in, which will ensure the script will work if Plex auth servers are down

* Useful for libraries stored on NAS shares where PMS cannot detect changes

* Tests PMS connection via command button from NZBGet Web UI

* Grabs list of your Plex library names and section numbers for configuring refresh modes

## Installation 

* Clone repository into your NZBGet scripts directory

    `git clone https://github.com/mannibis/NotifyPlex.git`

* Set permissions on NotifyPlex folder inside scripts directory. Script user should have write privileges in order to store 
auth token.    

* Configure variables within NZBGet Web UI. Select Library Refresh Mode:

    * **Auto:** This mode will use the NZBGet categories specified in the 'moviesCat' and 'tvCat' sections
    and when detected, will refresh the Plex sections associated with TV Shows or Movies automatically
    
    * **Custom:** This mode will use the numerical section numbers specified in the 'customPlexSection'
    option and refresh all of them upon successful download. Use 'Get Plex Sections' command button to 
    grab list of your Plex libraries and their corresponding section numbers
    
    * **Both:** This mode will use both the Auto and Custom modes
    
    * **Advanced:** This mode is for advanced users and will refresh Plex sections according to 
    a custom category:section_title mapping specified in the 'sectionMapping' option. Only one plex section
    will be refreshed depending on the NZBGet category. *Example:* `movies:Movies,uhd:Movies 4K,tv:TV Shows`
    will only refresh the "Movies" library if the NZBGet category detected was "movies", and so on.  The Plex 
    library names should match exactly as shown in your Plex server. Use 'Get Plex Sections' command button 
    to grab list of your Plex library names

* Enable script in 'CATEGORIES' settings or 'EXTENSION SCRIPTS' settings within NZBGet Web UI

* Optionally test PMS connection and plex.tv authorization by pressing 'Test PMS Connection' button on settings page

* To grab list of your Plex library names and section numbers, use 'Get Sections List' command button on settings page

**NOTE:** Plex Username and Password are only required to fetch auth token, which will be stored inside your NotifyPlex 
folder and subsequently re-used

**NOTE 2:** In the case that the auth token becomes invalid and library refreshes are not authorized, the script
should automatically delete the `plex_auth.ini` file. Simply re-run the script to force another sign-in and store
a new auth token