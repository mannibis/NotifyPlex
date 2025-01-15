#!/usr/bin/env python
"""
##############################################################################
### NZBGET POST-PROCESSING SCRIPT                                          ###

# Post-Processing Script to Update Plex Library and Notify PHT.
#
# This script triggers a targeted library update to your Plex Media Server and sends a GUI Notification to Plex Home Theater.
# Auto-Detection of NZBGet category and Plex sections is now supported. This script also works with Plex Home enabled.
#
# Copyright (C) 2020 mannibis
# Version 3.4
#
#
# NOTE: This script requires Python 3.x and the "requests" module to be installed on your system.

##############################################################################
### OPTIONS                                                                ###

## General

# Refresh Plex Library (yes,no).
#
# Activate if you want NotifyPlex to refresh your Plex library
#refreshLibrary=yes

# Send GUI Notification to Plex Home Theater (yes,no).
#
# Activate if you want NotifyPlex to Send a GUI notification to Plex Home Theater
#guiShow=yes

# Use Direct NZB ProperName for notification (yes,no).
#
# Activate if you want to use the DNZB Header ProperName for the title of the media if available
#dHeaders=yes

# Directory to store the auth token.
#plexAuthDir=

## Plex Media Server

# Plex Media Server Settings.
#
# Host IP of your Plex Media Server including port (only 1 server is supported)
#plexIP=192.168.1.XXX:32400

#
# Use Secure Connection (yes, no).
#plexSecure=no

# Plex.tv Username [Required]
#plexUser=
# Plex.tv Password [Required]
#plexPass=

# To test Plex Media Server connection and authorization, Save IP:Port, username, and password settings and click button.
#ConnectionTest@Test PMS Connection

# Library Refresh Mode (Auto,Custom,Both,Advanced).
#
# Select Refresh Mode: Auto will automatically detect your NZBGet category and refresh the appropriate sections,
# Custom will only refresh the sections you input into the Custom sections setting below, Both will auto-detect and refresh the Custom Sections,
# Advanced will use the section mapping specified in the sectionMapping option and only refresh one specific section
#refreshMode=Auto

# To test Plex Media Server refresh mode (Movies Category)
#RefreshModeTestMovies@Test PMS Refresh Movies

# To test Plex Media Server refresh mode (TV Category)
#RefreshModeTestTV@Test PMS Refresh TV

# NZBGet Movies Category/Categories [Required for Auto Mode].
#
# List the name(s) of your NZBGet categories (CategoryX.Name) that correspond to Movies (comma separated)
#moviesCat=movies

# NZBGet TV Category/Categories [Required for Auto Mode].
#
# List the name(s) of your NZBGet categories (CategoryX.Name) that correspond to TV Shows (comma separated)
#tvCat=tv

# Custom Plex Section(s) you would like to update [Optional].
#
# Section Number(s) corresponding to your Plex library (comma separated). These sections will only refreshed if Library Refesh Mode is set to Custom or Both
#customPlexSection=

# Advanced Section Mapping [Optional].
#
# Comma separated list of NZBGet categories mapped to Plex library names. Example: movies:Movies,uhd:4K Movies,tv:TV Shows
# To use this mode, select Advanced as your Library Refresh Mode. Only specific Plex libraries will be refreshed
# according to the NZBGet category used. Enter the exact names of your NZBGet categories and the exact names of your Plex libraries
#
#sectionMapping=

# Click button to grab list of your Plex libraries and corresponding section numbers.
#SectionList@Get Plex Sections

## Plex Home Theater

# Plex Home Theater Settings [Optional].
#
# Host IP(s) of your Plex Home Theater client(s) (comma separated)
#clientsIP=192.168.1.XXX

#
# Use Secure Connection (yes, no).
#clientsSecure=no

# Use Silent Failure Mode (yes,no).
#
# Activate if you want NZBGet to report a SUCCESS status regardless of errors, in cases where PMS is offline.
#silentFailure=no

### NZBGET POST-PROCESSING SCRIPT                                          ###
##############################################################################
"""  # noqa: E501

import contextlib
import http
import logging
import os
import pickle
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import requests

logger = logging.getLogger(__name__)

POSTPROCESS_SUCCESS = 93
POSTPROCESS_ERROR = 94
POSTPROCESS_NONE = 95

nzb_name = os.getenv("NZBPP_NZBNAME", "")
gui_show = os.getenv("NZBPO_GUISHOW", "no") == "yes"
refresh_library = os.getenv("NZBPO_REFRESHLIBRARY", "no") == "yes"
refresh_mode = os.getenv("NZBPO_REFRESHMODE", "")
silent_mode = os.getenv("NZBPO_SILENTFAILURE", "no") == "yes"
section_mapping = os.getenv("NZBPO_SECTIONMAPPING", "")

plex_secure_connection = os.getenv("NZBO_PLEXSECURE", "") == "yes"
plex_username = os.getenv("NZBPO_PLEXUSER", "")
plex_password = os.getenv("NZBPO_PLEXPASS", "")
plex_ip = os.getenv("NZBPO_PLEXIP", "")
plex_secure = os.getenv("NZBPO_PLEXSECURE", "no") == "yes"
script_dir = Path(os.getenv("NZBPO_SCRIPTDIR", ""))
notifyplex_directory = Path(__file__).parent.resolve()
plex_auth_dir = Path(os.getenv("NZBPO_PLEXAUTHDIR") or notifyplex_directory)
plex_auth_path = Path(plex_auth_dir, "plex_auth.ini")

proper_name = os.getenv("NZBPR__DNZB_PROPERNAME", "")
proper_ep = os.getenv("NZBPR__DNZB_EPISODENAME", "")
proper_year = os.getenv("NZBPR__DNZB_MOVIEYEAR", "")


def get_auth_token(test_mode: bool) -> str:
    if plex_auth_path.is_file() and not test_mode:
        with plex_auth_path.open("rb") as f:
            plex_dict = pickle.load(f)  # noqa: S301
            with contextlib.suppress(KeyError):
                auth_token = plex_dict["auth_token"]
                logger.info("USING STORED PLEX AUTH TOKEN. BYPASSING plex.tv")
                return auth_token

    auth_url = "https://plex.tv/users/sign_in.xml"
    auth_params = {"user[login]": plex_username, "user[password]": plex_password}
    headers = {
        "X-Plex-Platform": "NZBGet",
        "X-Plex-Platform-Version": "21.0",
        "X-Plex-Provides": "controller",
        "X-Plex-Product": "NotifyPlex",
        "X-Plex-Version": "3.3",
        "X-Plex-Device": "NZBGet",
        "X-Plex-Client-Identifier": "12286",
    }
    try:
        auth_request = requests.post(auth_url, headers=headers, data=auth_params, timeout=30, verify=True)
        auth_response = auth_request.content
        root = ET.fromstring(auth_response)  # noqa: S314
        try:
            plex_auth_token = root.attrib["authToken"]
            plex_dict = {"auth_token": plex_auth_token}
            if not test_mode:
                logger.info("plex.tv AUTHENTICATION SUCCESSFUL. STORING AUTH TOKEN TO %s", str(plex_auth_path))
                try:
                    plex_auth_path.parent.mkdir(parents=True, exist_ok=True)
                    with plex_auth_path.open("wb") as f:
                        logger.debug("STORING AUTH TOKEN TO: %s", str(plex_auth_path))
                        pickle.dump(plex_dict, f)
                except PermissionError:
                    logger.warning(
                        (
                            "CANNOT WRITE TO %s. PLEASE SET PROPER PERMISSIONS ON YOUR NOTIFYPLEX "
                            "FOLDER IF YOU WANT TO STORE AUTH TOKEN"
                        ),
                        str(plex_auth_path),
                        exc_info=True,
                    )
        except KeyError:
            if test_mode:
                logger.exception("ERROR AUTHENTICATING WITH plex.tv SERVERS. CHECK USERNAME/PASSWORD AND RETRY TEST")
                sys.exit(POSTPROCESS_ERROR)
            if silent_mode:
                logger.warning("ERROR AUTHENTICATING WITH plex.tv SERVERS. SILENT FAILURE MODE ACTIVATED")
                sys.exit(POSTPROCESS_SUCCESS)
            else:
                logger.exception("ERROR AUTHENTICATING WITH plex.tv SERVERS. TRY AGAIN")
                sys.exit(POSTPROCESS_ERROR)
        else:
            return plex_auth_token
    except (requests.exceptions.RequestException, OSError):
        if silent_mode:
            logger.warning("ERROR CONNECTING WITH plex.tv SERVERS. SILENT FAILURE MODE ACTIVATED")
            sys.exit(POSTPROCESS_SUCCESS)
        else:
            logger.exception("ERROR CONNECTING WITH plex.tv SERVERS. TRY AGAIN")
            sys.exit(POSTPROCESS_ERROR)


def create_plex_session(test_mode: bool) -> requests.Session:
    auth_token = get_auth_token(test_mode)
    session = requests.Session()
    session.verify = False
    session.params = {"X-Plex-Token": auth_token}
    return session


def get_plex_sections(session: requests.Session) -> list[tuple[str, str, str]]:
    """
    Gets the plex sections.

    Args:
        session (requests.Session): The session.

    Returns:
        list of tuples containing key, type, title.
    """
    section_url = f"{get_http_scheme(plex_secure)}://{plex_ip}/library/sections"
    try:
        response = session.get(section_url, timeout=10)
    except (requests.exceptions.RequestException, OSError):
        if silent_mode:
            logger.warning("ERROR AUTO-DETECTING PLEX SECTIONS. SILENT FAILURE MODE ACTIVATED")
            sys.exit(POSTPROCESS_SUCCESS)
        else:
            logger.exception("ERROR AUTO-DETECTING PLEX SECTIONS. CHECK CONNECTION DETAILS AND TRY AGAIN")
            sys.exit(POSTPROCESS_ERROR)

    if response.status_code == http.HTTPStatus.OK:
        root = ET.fromstring(response.text)  # noqa: S314
        sections: list[tuple[str, str, str]] = [
            (directory.get("key", ""), directory.get("type", ""), directory.get("title", ""))
            for directory in root.findall("Directory")
        ]

        sections.sort(key=lambda section: section[0])  # sort by the section number
        return sections

    if response.status_code == http.HTTPStatus.UNAUTHORIZED:
        try:
            if plex_auth_path.is_file():
                plex_auth_path.unlink()
        except PermissionError:
            pass
        if silent_mode:
            logger.warning(
                "AUTHORIZATION ERROR. PLEASE RE-RUN SCRIPT TO GENERATE NEW TOKEN. SILENT FAILURE MODE ACTIVATED"
            )
            sys.exit(POSTPROCESS_SUCCESS)
        else:
            logger.error("AUTHORIZATION ERROR. TOKEN MAY BE INVALID. PLEASE RE-RUN SCRIPT TO GENERATE NEW TOKEN")
            sys.exit(POSTPROCESS_ERROR)

    logger.error("UNKNOWN ERROR %d.", response.status_code)
    sys.exit(POSTPROCESS_ERROR)


def refresh_advanced(session: requests.Session, mapping: str, nzb_cat: str) -> None:
    category = None
    plex_section_title = None
    section_key = None
    section_map_list = mapping.split(",")
    for cur_section_map in section_map_list:
        section_map = cur_section_map.strip(" ")
        map_category = section_map.split(":")[0]
        if nzb_cat.casefold() == map_category.casefold():
            category = map_category
            plex_section_title = section_map.split(":")[1]
            break
    if category is None or plex_section_title is None:
        logger.debug("NZBGET CATEGORY FOR THIS DOWNLOAD IS: %s", nzb_cat)
        logger.error(
            "ERROR DETECTING NZBGET CATEGORY OR PLEX SECTION TITLE. PLEASE MAKE SURE YOUR SECTION "
            "MAPPING IS CORRECT AND TRY AGAIN"
        )
        sys.exit(POSTPROCESS_ERROR)

    sections = get_plex_sections(session)
    section_keys = [key for key, _type, title in sections if title.casefold() == plex_section_title.casefold()]
    if not section_keys:
        logger.debug('PLEX SECTION "%s" NOT FOUND ON YOUR SERVER', plex_section_title)
        logger.error("PLEX SECTION NOT FOUND. PLEASE MAKE SURE YOUR SECTION MAPPING IS CORRECT AND TRY AGAIN")
        sys.exit(POSTPROCESS_ERROR)

    section_key = section_keys[0]
    refresh_url = f"{get_http_scheme(plex_secure)}://{plex_ip}/library/sections/{section_key}/refresh"
    try:
        r = session.get(refresh_url, timeout=10)
        r.raise_for_status()
    except (requests.exceptions.RequestException, OSError):
        if silent_mode:
            logger.warning("ERROR UPDATING SECTION %s. SILENT FAILURE MODE ACTIVATED", section_key)
            sys.exit(POSTPROCESS_SUCCESS)
        else:
            logger.exception("ERROR UPDATING SECTION %s. CHECK CONNECTION DETAILS AND TRY AGAIN", section_key)
            sys.exit(POSTPROCESS_ERROR)
    logger.debug('REFRESHING PLEX SECTION "%s" MAPPED TO "%s" CATEGORY', plex_section_title, category)
    logger.info("TARGETED PLEX UPDATE FOR SECTION %s COMPLETE", section_key)


def refresh_section(session: requests.Session, nzb_cat: str, category: str, key: str, title: str) -> None:
    refresh_url = f"{get_http_scheme(plex_secure)}://{plex_ip}/library/sections/{key}/refresh"
    try:
        r = session.get(refresh_url, timeout=10)
        r.raise_for_status()
    except (requests.exceptions.RequestException, OSError):
        if silent_mode:
            logger.warning("ERROR UPDATING SECTION %s: %s. SILENT FAILURE MODE ACTIVATED", key, title)
            sys.exit(POSTPROCESS_SUCCESS)
        else:
            logger.exception("ERROR UPDATING SECTION %s: %s. CHECK CONNECTION DETAILS AND TRY AGAIN", key, title)
            sys.exit(POSTPROCESS_ERROR)
    logger.debug('AUTO-DETECTED "%s" CATEGORY. REFRESHING ALL "%s" LIBRARIES ON YOUR SERVER', nzb_cat, category)
    logger.info("TARGETED PLEX UPDATE FOR SECTION %s: %s COMPLETE", key, title)


def refresh_auto(session: requests.Session, movie_cats: str, tv_cats: str, nzb_cat: str) -> None:
    movie_cats = movie_cats.casefold().replace(" ", "")
    movie_cats_split = movie_cats.split(",")
    tv_cats = tv_cats.casefold().replace(" ", "")
    tv_cats_split = tv_cats.split(",")
    nzb_cat = nzb_cat.casefold()

    sections = get_plex_sections(session)
    movie_sections = []
    tv_sections = []

    logger.info(
        "Checking if %s is in Movies: %s or TV: %s categories.",
        nzb_cat,
        sorted(movie_cats_split),
        sorted(tv_cats_split),
    )
    for key, type_, title in sections:
        if type_ == "show":
            tv_sections.append((key, title))
        elif type_ == "movie":
            movie_sections.append((key, title))

    if nzb_cat in tv_cats_split:
        for key, title in tv_sections:
            refresh_section(session, nzb_cat, "show", key, title)

    if nzb_cat in movie_cats_split:
        for key, title in movie_sections:
            refresh_section(session, nzb_cat, "movie", key, title)


def refresh_custom_sections(session: requests.Session, raw_plex_sections: str) -> None:
    plex_sections = raw_plex_sections.replace(" ", "")
    plex_sections_split = plex_sections.split(",")

    for plex_section in plex_sections_split:
        refresh_url = f"{get_http_scheme(plex_secure)}://{plex_ip}/library/sections/{plex_section}/refresh"
        try:
            r = session.get(refresh_url, timeout=10)
            r.raise_for_status()
        except (requests.exceptions.RequestException, OSError):
            if silent_mode:
                logger.warning("ERROR UPDATING SECTION %s. SILENT FAILURE MODE ACTIVATED", plex_section)
                sys.exit(POSTPROCESS_SUCCESS)
            else:
                logger.exception(
                    "ERROR OPENING URL. CHECK NETWORK CONNECTION, PLEX SERVER IP:PORT, AND SECTION NUMBERS"
                )
                sys.exit(POSTPROCESS_ERROR)
        logger.info("TARGETED PLEX UPDATE FOR SECTION %s COMPLETE", plex_section)


def get_http_scheme(secure: bool) -> str:
    return "https" if secure else "http"


def show_gui_notification(raw_pht_ips: str) -> None:
    d_headers = os.getenv("NZBPO_DHEADERS", "no") == "yes"
    use_secure_conn = os.getenv("NZBPO_CLIENTSSECURE", "no") == "yes"
    pht_url = raw_pht_ips.replace(" ", "")
    pht_url_split = pht_url.split(",")
    with requests.Session() as session:
        session.headers = {"content-type": "application/json"}
        session.verify = False
        for pht_url in pht_url_split:
            if d_headers:
                if proper_name and proper_ep:
                    gui_text = f"{proper_name} - {proper_ep}"
                elif proper_name and proper_year:
                    gui_text = f"{proper_name} ({proper_year})"
                elif not proper_name and not proper_ep:
                    gui_text = nzb_name
                else:
                    gui_text = proper_name
            else:
                gui_text = nzb_name

            pht_rpc_url = f"{get_http_scheme(use_secure_conn)}://{pht_url}:3005/jsonrpc"
            payload = {
                "id": 1,
                "jsonrpc": "2.0",
                "method": "GUI.ShowNotification",
                "params": {"title": "Downloaded", "message": gui_text},
            }
            try:
                session.post(pht_rpc_url, json=payload, timeout=10)
                logger.info("PHT GUI NOTIFICATION TO %s SUCCESSFUL", pht_url)
            except (requests.exceptions.RequestException, OSError):
                logger.warning("PHT GUI NOTIFICATION TO %s FAILED", pht_url, exc_info=True)


def main() -> None:  # noqa: C901, PLR0912, PLR0915
    command = os.getenv("NZBCP_COMMAND")
    test_mode = command == "ConnectionTest"
    refresh_mode_test = command in ("RefreshModeTestTV", "RefreshModeTestMovies")
    list_sections_mode = command == "SectionList"
    session: requests.Session

    if (command is not None) and (not test_mode) and (not list_sections_mode) and (not refresh_mode_test):
        logger.error("INVALID COMMAND %s", command)
        sys.exit(POSTPROCESS_ERROR)

    if list_sections_mode:
        required_test_option = "NZBPO_PLEXIP"

        if required_test_option not in os.environ:
            logger.error(
                "OPTION %s IS MISSING IN CONFIGURATION FILE. PLEASE CHECK SCRIPT SETTINGS", required_test_option[6:]
            )
            sys.exit(POSTPROCESS_ERROR)

        logger.info("GRABBING LIST OF PLEX LIBRARIES AND SECTION NUMBERS")

        with create_plex_session(test_mode) as session:
            sections = get_plex_sections(session)

        logger.info("YOU HAVE A TOTAL OF %d SECTIONS", len(sections))
        for key, type_, title in sections:
            logger.info("SECTION %s: %s, type=%s", key, title, type_)
        sys.exit(POSTPROCESS_SUCCESS)

    if test_mode:
        required_test_options = ("NZBPO_PLEXUSER", "NZBPO_PLEXPASS", "NZBPO_PLEXIP")
        for optname in required_test_options:
            if optname not in os.environ:
                logger.error("OPTION %s IS MISSING IN CONFIGURATION FILE. PLEASE CHECK SCRIPT SETTINGS", optname[6:])
                sys.exit(POSTPROCESS_ERROR)
        plex_test_ip = os.getenv("NZBPO_PLEXIP", "")

        logger.info("TESTING PMS CONNECTION AND AUTHORIZATION")
        test_url = f"{get_http_scheme(plex_secure)}://{plex_test_ip}/library/sections"
        try:
            with create_plex_session(test_mode) as session:
                session.get(test_url, timeout=10)
        except requests.HTTPError as e:
            if e.response.status_code == http.HTTPStatus.UNAUTHORIZED:
                logger.exception("AUTHORIZATION ERROR. CHECK CONNECTION DETAILS AND RETRY TEST")
            else:
                logger.exception("ERROR CONNECTING TO PMS. CHECK CONNECTION DETAILS AND RETRY TEST")
            sys.exit(POSTPROCESS_ERROR)
        logger.info("CONNECTION TEST SUCCESSFUL!")
        sys.exit(POSTPROCESS_SUCCESS)

    required_options = (
        "NZBPO_PLEXIP",
        "NZBPO_SILENTFAILURE",
        "NZBPO_REFRESHMODE",
        "NZBPO_REFRESHLIBRARY",
        "NZBPO_DHEADERS",
        "NZBPO_GUISHOW",
    )

    missing_options = sorted(optname[6:] for optname in required_options if optname not in os.environ)
    if missing_options:
        logger.error("OPTIONS %s MISSING IN CONFIGURATION FILE. PLEASE CHECK SCRIPT SETTINGS", missing_options)
        sys.exit(POSTPROCESS_ERROR)

    nzb_cat = os.getenv("NZBPP_CATEGORY", "")
    # Check to see if download was successful
    if refresh_mode_test:
        pp_status = True
        if command == "RefreshModeTestTV":
            nzb_cat = "TV"
        elif command == "RefreshModeTestMovies":
            nzb_cat = "Movies"

    elif "NZBPP_STATUS" in os.environ:
        pp_status = os.environ["NZBPP_STATUS"].startswith("SUCCESS/")
    else:
        logger.info("*** NZBGet post-processing script ***")
        logger.info("This script is supposed to be called from NZBGet v13.0 or later.")
        sys.exit(POSTPROCESS_ERROR)

    if pp_status:
        if gui_show:
            pht_urls = os.getenv("NZBPO_CLIENTSIP", "")
            show_gui_notification(pht_urls)

        if refresh_library:
            raw_plex_section = os.getenv("NZBPO_CUSTOMPLEXSECTION", "")
            movie_cats = os.getenv("NZBPO_MOVIESCAT", "")
            tv_cats = os.getenv("NZBPO_TVCAT", "")

            with create_plex_session(test_mode) as session:
                if refresh_mode == "Custom":
                    refresh_custom_sections(session, raw_plex_section)
                elif refresh_mode == "Auto":
                    refresh_auto(session, movie_cats, tv_cats, nzb_cat)
                elif refresh_mode == "Advanced":
                    refresh_advanced(session, section_mapping, nzb_cat)
                else:
                    refresh_custom_sections(session, raw_plex_section)
                    refresh_auto(session, movie_cats, tv_cats, nzb_cat)

        sys.exit(POSTPROCESS_SUCCESS)

    else:
        logger.error("SKIPPING PLEX UPDATE BECAUSE DOWNLOAD FAILED.")
        sys.exit(POSTPROCESS_NONE)


if __name__ == "__main__":
    import urllib3

    urllib3.disable_warnings(category=urllib3.exceptions.InsecureRequestWarning)

    logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(asctime)s\t%(message)s")

    main()
