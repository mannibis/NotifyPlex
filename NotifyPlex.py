#!/usr/bin/env python2
#
##############################################################################
### NZBGET POST-PROCESSING SCRIPT                                          ###

# Post-Processing Script to Update Plex Library and Notify PHT.
#
# This script triggers a targeted library update to your Plex Media Server and sends a GUI Notification to Plex Home Theater.
# Auto-Detection of NZBGet category and Plex sections is now supported. This script also works with Plex Home enabled.
#
# Copyright (C) 2020 mannibis
# Version 2.6
#
#
# NOTE: This script requires Python 2.x and the "requests" module to be installed on your system.

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

## Plex Media Server

# Plex Media Server Settings.
#
# Host IP of your Plex Media Server including port (only 1 server is supported)
#plexIP=192.168.1.XXX:32400

# Plex.tv Username [Required]
#plexUser=
# Plex.tv Password [Required]
#plexPass=

# Library Refresh Mode (Auto,Custom,Both).
#
# Select Refresh Mode: Auto will automatically detect your NZBGet category and refresh the appropriate sections, Custom will only refresh the sections you input into the Custom sections setting below, Both will auto-detect and refresh the Custom Sections
#refreshMode=Auto

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

## Plex Home Theater

# Plex Home Theater Settings [Optional].
#
# Host IP(s) of your Plex Home Theater client(s) (comma separated)
#clientsIP=192.168.1.XXX

# Use Silent Failure Mode (yes,no).
#
# Activate if you want NZBGet to report a SUCCESS status regardless of errors, in cases where PMS is offline.
#silentFailure=no

### NZBGET POST-PROCESSING SCRIPT                                          ###
##############################################################################

import os
import sys
import requests
import json
import xml.etree.ElementTree as ET
import pickle

POSTPROCESS_SUCCESS = 93
POSTPROCESS_ERROR = 94
POSTPROCESS_NONE = 95

if 'NZBPP_STATUS' not in os.environ:
	print('*** NZBGet post-processing script ***')
	print('This script is supposed to be called from NZBGet v13.0 or later.')
	sys.exit(POSTPROCESS_ERROR)

required_options = ('NZBPO_SILENTFAILURE', 'NZBPO_MOVIESCAT', 'NZBPO_TVCAT', 'NZBPO_REFRESHMODE', 'NZBPO_REFRESHLIBRARY', 'NZBPO_DHEADERS', 'NZBPO_GUISHOW', 'NZBPO_PLEXUSER', 'NZBPO_PLEXPASS')
for optname in required_options:
	if optname not in os.environ:
		print('[ERROR] NOTIFYPLEX: OPTION %s IS MISSING IN CONFIGURATION FILE. PLEASE CHECK SCRIPT SETTINGS' % optname[6:])
		sys.exit(POSTPROCESS_ERROR)

# Check to see if download was successful
pp_status = os.environ['NZBPP_STATUS'].startswith('SUCCESS/')

dnzboptions = ('NZBPR__DNZB_PROPERNAME', 'NZBPR__DNZB_EPISODENAME', 'NZBPR__DNZB_MOVIEYEAR')
if dnzboptions[0] in os.environ:
	proper_name = os.environ[dnzboptions[0]]
else:
	proper_name = ''
if dnzboptions[1] in os.environ:
	proper_ep = os.environ[dnzboptions[1]]
else:
	proper_ep = ''
if dnzboptions[2] in os.environ:
	proper_year = os.environ[dnzboptions[2]]
else:
	proper_year = ''

nzb_name = os.environ['NZBPP_NZBNAME']
nzb_cat = os.environ['NZBPP_CATEGORY']
gui_show = os.environ['NZBPO_GUISHOW'] == 'yes'
plex_username = os.environ['NZBPO_PLEXUSER']
plex_password = os.environ['NZBPO_PLEXPASS']
refresh_library = os.environ['NZBPO_REFRESHLIBRARY'] == 'yes'
refresh_mode = os.environ['NZBPO_REFRESHMODE']
silent_mode = os.environ['NZBPO_SILENTFAILURE'] == 'yes'


def get_auth_token(plex_user, plex_pass):
	if os.path.isfile('plex_auth.ini'):
		with open('plex_auth.ini', 'r') as f:
			plex_dict = pickle.load(f)
		print('[INFO] NOTIFYPLEX: USING STORED PLEX AUTH TOKEN. BYPASSING plex.tv')
		return plex_dict.get('auth_token')

	auth_url = 'https://my.plexapp.com/users/sign_in.xml'
	auth_params = {'user[login]': plex_user, 'user[password]': plex_pass}
	headers = {
			'X-Plex-Platform': 'NZBGet',
			'X-Plex-Platform-Version': '21.0',
			'X-Plex-Provides': 'controller',
			'X-Plex-Product': 'NotifyPlex',
			'X-Plex-Version': "2.6",
			'X-Plex-Device': 'NZBGet',
			'X-Plex-Client-Identifier': '12286'
	}
	try:
		auth_request = requests.post(auth_url, headers=headers, data=auth_params)
		auth_response = auth_request.content
		root = ET.fromstring(auth_response)
		try:
			plex_auth_token = root.attrib['authToken']
			print('[INFO] NOTIFYPLEX: plex.tv AUTHENTICATION SUCCESSFUL. STORING AUTH TOKEN TO DISK')
			with open('plex_auth.ini', 'w') as f:
				pickle.dump({'auth_token': plex_auth_token}, f)
			return plex_auth_token
		except KeyError:
			if silent_mode:
				print ('[WARNING] NOTIFYPLEX: ERROR AUTHENTICATING WITH plex.tv. USERNAME/PASSWORD INCORRECT. SILENT FAILURE MODE ACTIVATED')
				sys.exit(POSTPROCESS_SUCCESS)
			else:
				print ('[ERROR] NOTIFYPLEX: ERROR AUTHENTICATING WITH plex.tv. USERNAME/PASSWORD INCORRECT')
				sys.exit(POSTPROCESS_ERROR)
	except requests.exceptions.Timeout or requests.exceptions.HTTPError or requests.exceptions.ConnectionError:
		if silent_mode:
			print ('[WARNING] NOTIFYPLEX: THERE WAS AN ERROR AUTHENTICATING WITH plex.tv. SILENT FAILURE MODE ACTIVATED')
			sys.exit(POSTPROCESS_SUCCESS)
		else:
			print ('[ERROR] NOTIFYPLEX: ERROR AUTHENTICATING WITH plex.tv')
			sys.exit(POSTPROCESS_ERROR)


def refresh_auto(movie_cats, tv_cats, plex_ip):

	movie_cats = movie_cats.replace(' ', '')
	movie_cats_split = movie_cats.split(',')
	tv_cats = tv_cats.replace(' ', '')
	tv_cats_split = tv_cats.split(',')

	params = {
		'X-Plex-Token': get_auth_token(plex_username, plex_password)
	}

	url = 'http://%s/library/sections' % plex_ip
	try:
		section_request = requests.get(url, params=params, timeout=10)
		section_response = section_request.content
	except requests.exceptions.Timeout or requests.exceptions.HTTPError or requests.exceptions.ConnectionError:
		if silent_mode:
			print ('[WARNING] NOTIFYPLEX: ERROR AUTO-DETECTING PLEX SECTIONS. SILENT FAILURE MODE ACTIVATED')
			sys.exit(POSTPROCESS_SUCCESS)
		else:
			print ('[ERROR] NOTIFYPLEX: ERROR AUTO-DETECTING PLEX SECTIONS. CHECK NETWORK CONNECTION AND PLEX SERVER IP:PORT')
			sys.exit(POSTPROCESS_ERROR)

	root = ET.fromstring(section_response)
	movie_sections = []
	tv_sections = []

	for directory in root.findall('Directory'):
		video_type = directory.get('type')
		if video_type == 'show':
			tv_sections.append(directory.get('key'))
		elif video_type == 'movie':
			movie_sections.append(directory.get('key'))

	for tv_cat in tv_cats_split:
		if nzb_cat == tv_cat:
			for tv_section in tv_sections:
				refresh_url = 'http://%s/library/sections/%s/refresh' % (plex_ip, tv_section)
				try:
					requests.get(refresh_url, params=params, timeout=10)
				except requests.Timeout or requests.ConnectionError or requests.HTTPError:
					if silent_mode:
						print ('[WARNING] NOTIFYPLEX: ERROR UPDATING SECTION %s. SILENT FAILURE MODE ACTIVATED' % tv_section)
						sys.exit(POSTPROCESS_SUCCESS)
					else:
						print ('[ERROR] NOTIFYPLEX: ERROR OPENING URL. CHECK NETWORK CONNECTION, PLEX SERVER IP:PORT, AND SECTION NUMBERS')
						sys.exit(POSTPROCESS_ERROR)
				print ('[INFO] NOTIFYPLEX: TARGETED PLEX UPDATE FOR SECTION %s COMPLETE' % tv_section)

	for movie_cat in movie_cats_split:
		if nzb_cat == movie_cat:
			for movie_section in movie_sections:
				section_url = 'http://%s/library/sections/%s/refresh' % (plex_ip, movie_section)
				try:
					requests.get(section_url, params=params, timeout=10)
				except requests.Timeout or requests.ConnectionError or requests.HTTPError:
					if silent_mode:
						print ('[WARNING] NOTIFYPLEX: ERROR UPDATING SECTION %s. SILENT FAILURE MODE ACTIVATED' % movie_section)
						sys.exit(POSTPROCESS_SUCCESS)
					else:
						print ('[ERROR] NOTIFYPLEX: ERROR OPENING URL. CHECK NETWORK CONNECTION, PLEX SERVER IP:PORT, AND SECTION NUMBERS')
						sys.exit(POSTPROCESS_ERROR)
				print ('[INFO] NOTIFYPLEX: TARGETED PLEX UPDATE FOR SECTION %s COMPLETE' % movie_section)


def refresh_custom_sections(raw_plex_sections, plex_ip):

	plex_sections = raw_plex_sections.replace(' ', '')
	plex_sections_split = plex_sections.split(',')

	params = {
		'X-Plex-Token': get_auth_token(plex_username, plex_password)
	}

	for plex_section in plex_sections_split:
		section_url = 'http://%s/library/sections/%s/refresh' % (plex_ip, plex_section)
		try:
			requests.get(section_url, params=params, timeout=10)
		except requests.exceptions.Timeout or requests.exceptions.HTTPError or requests.exceptions.ConnectionError:
			if silent_mode:
				print ('[WARNING] NOTIFYPLEX: ERROR UPDATING SECTION %s. SILENT FAILURE MODE ACTIVATED' % plex_section)
				sys.exit(POSTPROCESS_SUCCESS)
			else:
				print ('[ERROR] NOTIFYPLEX: ERROR OPENING URL. CHECK NETWORK CONNECTION, PLEX SERVER IP:PORT, AND SECTION NUMBERS')
				sys.exit(POSTPROCESS_ERROR)
		print ('[INFO] NOTIFYPLEX: TARGETED PLEX UPDATE FOR SECTION %s COMPLETE' % plex_section)


def show_gui_notification(raw_pht_ips):

	d_headers = os.environ['NZBPO_DHEADERS'] == 'yes'
	pht_url = raw_pht_ips.replace(' ', '')
	pht_url_split = pht_url.split(',')
	for pht_url in pht_url_split:
		if d_headers:
			if (proper_name != '') and (proper_ep != ''):
				gui_text = '%s - %s' % (proper_name, proper_ep)
			elif (proper_name != '') and (proper_year != ''):
				gui_text = '%s (%s)' % (proper_name, proper_year)
			elif (proper_name == '') and (proper_ep == ''):
				gui_text = nzb_name
			else:
				gui_text = proper_name
		else:
			gui_text = nzb_name

		pht_rpc_url = 'http://%s:3005/jsonrpc' % pht_url
		headers = {'content-type': 'application/json'}
		payload= {'id': 1, 'jsonrpc': '2.0', 'method': 'GUI.ShowNotification', 'params': {'title': 'Downloaded', 'message': gui_text}}
		try:
			requests.post(pht_rpc_url, data=json.dumps(payload), headers=headers, timeout=10)
			print ('[INFO] NOTIFYPLEX: GUI NOTIFICATION TO PHT INSTANCE SUCCESSFUL')
		except requests.exceptions.Timeout or requests.exceptions.HTTPError or requests.exceptions.ConnectionError:
			print ('[WARNING] NOTIFYPLEX: PHT GUI NOTIFICATION FAILED')


if pp_status:

	if gui_show:
		pht_urls = os.environ['NZBPO_CLIENTSIP']
		show_gui_notification(pht_urls)

	if refresh_library:
		plex_ip = os.environ['NZBPO_PLEXIP']
		raw_plex_section = os.environ['NZBPO_CUSTOMPLEXSECTION']
		movie_cats = os.environ['NZBPO_MOVIESCAT']
		tv_cats = os.environ['NZBPO_TVCAT']

		if refresh_mode == 'Custom':
			refresh_custom_sections(raw_plex_section, plex_ip)
		elif refresh_mode == 'Auto':
			refresh_auto(movie_cats, tv_cats, plex_ip)
		else:
			refresh_custom_sections(raw_plex_section, plex_ip)
			refresh_auto(movie_cats, tv_cats, plex_ip)

	sys.exit(POSTPROCESS_SUCCESS)

else:
	print ('[ERROR] NOTIFYPLEX: SKIPPING PLEX UPDATE BECAUSE DOWNLOAD FAILED.')
	sys.exit(POSTPROCESS_NONE)
