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

# To clear the stored auth token, delete the file.
#DeleteCacheFile@Delete the Stored Auth Token

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

from __future__ import annotations

import http
import logging
import os
import pickle
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, cast
from urllib.parse import urljoin

import requests

logger = logging.getLogger(__name__)

POSTPROCESS_SUCCESS = 93
POSTPROCESS_ERROR = 94
POSTPROCESS_NONE = 95

DEFAULT_PLEX_TV_TIMEOUT = 30
DEFAULT_PLEX_TIMEOUT = 10

NUMBER_RE = re.compile(r"\d+")

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


class _Session(requests.Session):
    def __init__(self, base_url: str) -> None:
        super().__init__()
        self.base_url = base_url

    def request(self, method: str | bytes, url: str | bytes, *args: Any, **kwargs: Any) -> requests.Response:  # noqa: ANN401
        return super().request(method, urljoin(self.base_url, cast(str, url)), *args, **kwargs)


def _get_direct_url_from_plex_tv(session: requests.Session, auth_token: str) -> str | None:
    url = "https://plex.tv/pms/resources?includeHttps=1"
    session.headers = {
        "X-Plex-Token": auth_token,
    }

    response = session.get(url, timeout=DEFAULT_PLEX_TV_TIMEOUT)
    if not response.ok:
        logger.error("ERROR CONNECTING TO plex.tv SERVERS. CHECK CONNECTION DETAILS AND TRY AGAIN")
        return None

    servers = ET.fromstring(response.text)  # noqa: S314
    plex_hostname = plex_ip.split(":")[0].casefold()  # looking for the specific hostname that matches the plexIP.

    for server in servers:
        for connection in server:
            address = connection.get("address")
            if address is None:
                continue

            if address.casefold() != plex_hostname:
                continue

            uri = connection.get("uri")
            if uri is None or "plex.direct" not in uri:
                continue

            r = session.options(urljoin(uri, "identity"), timeout=DEFAULT_PLEX_TIMEOUT)
            if r.status_code == http.HTTPStatus.OK:
                return uri

    return None


def _get_auth_token_from_plex_tv(session: requests.Session, test_mode: bool) -> str:
    auth_url = "https://plex.tv/users/sign_in.xml"
    auth_params = {"user[login]": plex_username, "user[password]": plex_password}
    headers = {
        "X-Plex-Platform": "NZBGet",
        "X-Plex-Platform-Version": "21.0",
        "X-Plex-Provides": "controller",
        "X-Plex-Product": "NotifyPlex",
        "X-Plex-Version": "3.4",
        "X-Plex-Device": "NZBGet",
        "X-Plex-Client-Identifier": "12286",
    }
    try:
        response = session.post(
            auth_url, headers=headers, data=auth_params, timeout=DEFAULT_PLEX_TV_TIMEOUT, verify=True
        )
        response.raise_for_status()
        root = ET.fromstring(response.text)  # noqa: S314
        try:
            plex_auth_token = root.attrib["authToken"]
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


def _read_from_cache_file() -> tuple[str | None, str | None]:
    if not plex_auth_path.is_file():
        return None, None

    try:
        with plex_auth_path.open("rb") as f:
            plex_dict = pickle.load(f)  # noqa: S301
            if "auth_token" not in plex_dict or "direct_url" not in plex_dict:
                return None, None

        logger.info("USING STORED PLEX AUTH TOKEN. BYPASSING plex.tv")
        return plex_dict["auth_token"], plex_dict["direct_url"]
    except (pickle.UnpicklingError, EOFError, OSError):
        logger.exception("ERROR READING %s", str(plex_auth_path))
        return None, None


def _write_cache_file(auth_token: str, direct_url: str | None) -> None:
    plex_dict = {"auth_token": auth_token, "direct_url": direct_url}
    try:
        plex_auth_path.parent.mkdir(parents=True, exist_ok=True)
        with plex_auth_path.open("wb") as f:
            logger.debug("STORING AUTH TOKEN TO: %s", str(plex_auth_path))
            pickle.dump(plex_dict, f)
    except PermissionError:
        logger.warning(
            ("CANNOT WRITE TO %s. PLEASE SET PROPER PERMISSIONS ON %s FOLDER IF YOU WANT TO STORE AUTH TOKEN"),
            str(plex_auth_path),
            str(plex_auth_path.parent),
            exc_info=True,
        )


def _delete_cache_file() -> None:
    if not plex_auth_path.is_file():
        return

    logger.info("REMOVING %s", str(plex_auth_path))
    try:
        plex_auth_path.unlink(missing_ok=True)
    except PermissionError:
        logger.warning(
            ("CANNOT DELETE %s. PLEASE SET PROPER PERMISSIONS ON %s FOLDER IF YOU WANT TO STORE AUTH TOKEN"),
            str(plex_auth_path),
            str(plex_auth_path.parent),
            exc_info=True,
        )


def get_auth_token(test_mode: bool) -> tuple[str, str | None]:
    auth_token = None
    if not test_mode:
        auth_token, direct_url = _read_from_cache_file()
        if auth_token is not None:
            return auth_token, direct_url

    with requests.Session() as session:
        auth_token = _get_auth_token_from_plex_tv(session, test_mode)
        direct_url = _get_direct_url_from_plex_tv(session, auth_token)

    if not test_mode:
        _write_cache_file(auth_token, direct_url)

    return auth_token, direct_url


def create_plex_session(test_mode: bool) -> requests.Session:
    auth_token, base_url = get_auth_token(test_mode)
    if base_url is None:
        base_url = f"{get_http_scheme(plex_secure)}://{plex_ip}"
        session = _Session(base_url=base_url)
    else:
        session = _Session(base_url=base_url)
    session.params = {"X-Plex-Token": auth_token}
    return session


def get_plex_sections(session: requests.Session) -> list[tuple[int, str, str]]:
    """
    Gets the plex sections.

    Args:
        session (requests.Session): The session.

    Returns:
        list of tuples containing key, type, title.
    """
    try:
        response = session.get("/library/sections", timeout=DEFAULT_PLEX_TIMEOUT)
        response.raise_for_status()
    except (requests.exceptions.RequestException, OSError):
        if silent_mode:
            logger.warning("ERROR AUTO-DETECTING PLEX SECTIONS. SILENT FAILURE MODE ACTIVATED")
            sys.exit(POSTPROCESS_SUCCESS)
        else:
            logger.exception("ERROR AUTO-DETECTING PLEX SECTIONS. CHECK CONNECTION DETAILS AND TRY AGAIN")
            sys.exit(POSTPROCESS_ERROR)

    if response.status_code == http.HTTPStatus.OK:
        root = ET.fromstring(response.text)  # noqa: S314
        sections: list[tuple[int, str, str]] = [
            (int(directory.get("key", "")), directory.get("type", ""), directory.get("title", ""))
            for directory in root.findall("Directory")
        ]

        sections.sort(key=lambda section: section[0])  # sort by the section number
        return sections

    if response.status_code == http.HTTPStatus.UNAUTHORIZED:
        _delete_cache_file()
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


def refresh_section(session: requests.Session, key: int, title: str) -> bool:
    refresh_url = f"/library/sections/{key}/refresh"
    try:
        response = session.get(refresh_url, timeout=DEFAULT_PLEX_TIMEOUT)
        response.raise_for_status()
        logger.info("TARGETED PLEX UPDATE FOR SECTION %s: %s COMPLETE", key, title)
    except (requests.exceptions.RequestException, OSError):
        if not silent_mode:
            logger.exception("ERROR UPDATING SECTION %s: %s. CHECK CONNECTION DETAILS AND TRY AGAIN", key, title)
            return False

        logger.warning("ERROR UPDATING SECTION %s: %s. SILENT FAILURE MODE ACTIVATED", key, title)

    return True


def refresh_advanced(session: requests.Session, mapping: str, nzb_cat: str) -> None:
    plex_section_titles: dict[str, str] = {}
    section_map_list = mapping.split(",")
    for cur_section_map in section_map_list:
        map_category, plex_section_title = cur_section_map.split(":")
        if nzb_cat.casefold() == map_category.strip(" ").casefold():
            plex_section_titles[plex_section_title.strip(" ").casefold()] = plex_section_title

    if not plex_section_titles:
        logger.debug("NZBGET CATEGORY FOR THIS DOWNLOAD IS: %s", nzb_cat)
        logger.error(
            "ERROR DETECTING NZBGET CATEGORY OR PLEX SECTION TITLE. PLEASE MAKE SURE YOUR SECTION "
            "MAPPING IS CORRECT AND TRY AGAIN"
        )
        sys.exit(POSTPROCESS_ERROR)

    sections = get_plex_sections(session)
    section_keys: list[tuple[int, str]] = []

    for key, _type, title in sections:
        title_key = title.strip(" ").casefold()
        if title_key in plex_section_titles:
            section_keys.append((key, title))
            plex_section_titles.pop(title_key)

    logger.debug("REFRESHING SECTIONS: %s LIBRARIES ON YOUR SERVER", sorted([key for key, _title in section_keys]))

    all_refreshed = True
    for key, title in section_keys:
        all_refreshed = refresh_section(session, key, title) and all_refreshed

    if plex_section_titles:
        logger.error(
            'PLEX SECTIONS: %s NOT FOUND. PLEASE MAKE SURE YOUR SECTION MAPPING IS CORRECT AND TRY AGAIN"',
            sorted(plex_section_titles.values()),
        )
        sys.exit(POSTPROCESS_ERROR)

    if not all_refreshed:
        sys.exit(POSTPROCESS_ERROR)


def refresh_auto(session: requests.Session, movie_cats: str, tv_cats: str, nzb_cat: str) -> None:
    movie_cats = movie_cats.casefold().replace(" ", "")
    movie_cats_split = movie_cats.split(",")
    tv_cats = tv_cats.casefold().replace(" ", "")
    tv_cats_split = tv_cats.split(",")
    nzb_cat = nzb_cat.casefold()

    sections = get_plex_sections(session)
    movie_sections: list[tuple[int, str]] = []
    tv_sections: list[tuple[int, str]] = []

    logger.debug(
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

    all_refreshed = True
    if nzb_cat in tv_cats_split:
        logger.debug(
            'AUTO-DETECTED "%s" CATEGORY. REFRESHING ALL %d "SHOW" LIBRARIES ON YOUR SERVER', nzb_cat, len(tv_sections)
        )
        for key, title in tv_sections:
            all_refreshed = refresh_section(session, key, title) and all_refreshed

    if nzb_cat in movie_cats_split:
        logger.debug(
            'AUTO-DETECTED "%s" CATEGORY. REFRESHING ALL %d "MOVIE" LIBRARIES ON YOUR SERVER',
            nzb_cat,
            len(movie_sections),
        )
        for key, title in movie_sections:
            all_refreshed = refresh_section(session, key, title) and all_refreshed

    if not all_refreshed:
        sys.exit(POSTPROCESS_ERROR)


def refresh_custom_sections(session: requests.Session, raw_plex_sections: str) -> None:
    plex_sections = {int(m) for m in NUMBER_RE.findall(raw_plex_sections)}

    sections = get_plex_sections(session)
    all_refreshed = True
    for key, _type, title in sections:
        if key not in plex_sections:
            continue
        all_refreshed = refresh_section(session, key, title) and all_refreshed
        plex_sections.remove(key)

    if plex_sections:
        logger.warning(
            "THE FOLLOWING SECTIONS ARE NOT FOUND ON YOUR SERVER: %s",
            sorted(plex_sections),
        )
        sys.exit(POSTPROCESS_ERROR)

    if not all_refreshed:
        sys.exit(POSTPROCESS_ERROR)


def get_http_scheme(secure: bool) -> str:
    return "https" if secure else "http"


def show_gui_notification(raw_pht_ips: str) -> None:
    d_headers = os.getenv("NZBPO_DHEADERS", "no") == "yes"
    use_secure_conn = os.getenv("NZBPO_CLIENTSSECURE", "no") == "yes"
    pht_url = raw_pht_ips.replace(" ", "")
    pht_url_split = pht_url.split(",")
    with requests.Session() as session:
        session.headers = {"content-type": "application/json"}
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
                response = session.post(pht_rpc_url, json=payload, timeout=DEFAULT_PLEX_TIMEOUT)
                if response.ok:
                    logger.info("PHT GUI NOTIFICATION TO %s SUCCESSFUL", pht_url)
                else:
                    logger.warning("PHT GUI NOTIFICATION TO %s FAILED WITH ERROR %d", pht_url, response.status_code)
            except (requests.exceptions.RequestException, OSError):
                logger.warning("PHT GUI NOTIFICATION TO %s FAILED", pht_url, exc_info=True)


def main() -> None:  # noqa: C901, PLR0912, PLR0915
    command = os.getenv("NZBCP_COMMAND")
    test_mode = command == "ConnectionTest"
    refresh_mode_test = command in ("RefreshModeTestTV", "RefreshModeTestMovies")
    list_sections_mode = command == "SectionList"
    delete_cache_file = command == "DeleteCacheFile"
    session: requests.Session

    if (
        (command is not None)
        and (not test_mode)
        and (not list_sections_mode)
        and (not refresh_mode_test)
        and (not delete_cache_file)
    ):
        logger.error("INVALID COMMAND %s", command)
        sys.exit(POSTPROCESS_ERROR)

    if delete_cache_file:
        _delete_cache_file()
        sys.exit(POSTPROCESS_SUCCESS)

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

        logger.info("TESTING PMS CONNECTION AND AUTHORIZATION")
        try:
            with create_plex_session(test_mode) as session:
                response = session.get("/library/sections", timeout=DEFAULT_PLEX_TIMEOUT)
                response.raise_for_status()
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
    logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(asctime)s\t%(message)s")

    main()
