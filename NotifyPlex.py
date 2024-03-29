#!/usr/bin/env python
#
##############################################################################
### NZBGET POST-PROCESSING SCRIPT                                          ###

# Post-Processing Script to Update Plex Library and Notify PHT.
#
# This script triggers a targeted library update to your Plex Media Server and sends a GUI Notification to Plex Home Theater.
# Auto-Detection of NZBGet category and Plex sections is now supported. This script also works with Plex Home enabled.
#
# Copyright (C) 2020 mannibis
# Version 3.3
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

## Plex Media Server

# Plex Media Server Settings.
#
# Host IP of your Plex Media Server including port (only 1 server is supported)
#plexIP=192.168.1.XXX:32400

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

plex_username = os.environ['NZBPO_PLEXUSER']
plex_password = os.environ['NZBPO_PLEXPASS']
plex_ip = os.environ['NZBPO_PLEXIP']
script_dir = os.environ['NZBOP_SCRIPTDIR']
notifyplex_directory = os.path.dirname(os.path.realpath(__file__))
plex_auth_path = os.path.join(script_dir, notifyplex_directory, 'plex_auth.ini')


def get_auth_token():
	if os.path.isfile(plex_auth_path) and not test_mode:
		with open(plex_auth_path, 'rb') as f:
			plex_dict = pickle.load(f)
		print('[INFO] USING STORED PLEX AUTH TOKEN. BYPASSING plex.tv')
		return plex_dict.get('auth_token')

	auth_url = 'https://plex.tv/users/sign_in.xml'
	auth_params = {'user[login]': plex_username, 'user[password]': plex_password}
	headers = {
			'X-Plex-Platform': 'NZBGet',
			'X-Plex-Platform-Version': '21.0',
			'X-Plex-Provides': 'controller',
			'X-Plex-Product': 'NotifyPlex',
			'X-Plex-Version': "3.3",
			'X-Plex-Device': 'NZBGet',
			'X-Plex-Client-Identifier': '12286'
	}
	try:
		auth_request = requests.post(auth_url, headers=headers, data=auth_params, timeout=30, verify=True)
		auth_response = auth_request.content
		root = ET.fromstring(auth_response)
		try:
			plex_auth_token = root.attrib['authToken']
			plex_dict = {'auth_token': plex_auth_token}
			if not test_mode:
				print('[INFO] plex.tv AUTHENTICATION SUCCESSFUL. STORING AUTH TOKEN TO DISK')
				try:
					with open(plex_auth_path, 'wb') as f:
						print('[DEBUG] STORING AUTH TOKEN TO: {}'.format(plex_auth_path))
						pickle.dump(plex_dict, f)
				except PermissionError:
					print('[WARNING] CANNOT WRITE TO DISK. PLEASE SET PROPER PERMISSIONS ON YOUR NOTIFYPLEX '
							'FOLDER IF YOU WANT TO STORE AUTH TOKEN')
			return plex_auth_token
		except KeyError:
			if test_mode:
				print('[ERROR] ERROR AUTHENTICATING WITH plex.tv SERVERS. CHECK USERNAME/PASSWORD AND RETRY TEST')
				sys.exit(POSTPROCESS_ERROR)
			if silent_mode:
				print('[WARNING] ERROR AUTHENTICATING WITH plex.tv SERVERS. SILENT FAILURE MODE ACTIVATED')
				sys.exit(POSTPROCESS_SUCCESS)
			else:
				print('[ERROR] ERROR AUTHENTICATING WITH plex.tv SERVERS. TRY AGAIN')
				sys.exit(POSTPROCESS_ERROR)
	except requests.exceptions.RequestException or OSError:
		requests.session().close()
		if silent_mode:
			print('[WARNING] ERROR CONNECTING WITH plex.tv SERVERS. SILENT FAILURE MODE ACTIVATED')
			sys.exit(POSTPROCESS_SUCCESS)
		else:
			print('[ERROR] ERROR CONNECTING WITH plex.tv SERVERS. TRY AGAIN')
			sys.exit(POSTPROCESS_ERROR)


def get_plex_sections():
	global params
	params = {
		'X-Plex-Token': get_auth_token()
	}
	section_url = 'http://{}/library/sections'.format(plex_ip)
	try:
		section_request = requests.get(section_url, params=params, timeout=10)
		section_response = section_request.content
	except requests.exceptions.RequestException or OSError:
		requests.session().close()
		if silent_mode:
			print('[WARNING] ERROR AUTO-DETECTING PLEX SECTIONS. SILENT FAILURE MODE ACTIVATED')
			sys.exit(POSTPROCESS_SUCCESS)
		else:
			print('[ERROR] ERROR AUTO-DETECTING PLEX SECTIONS. CHECK CONNECTION DETAILS AND TRY AGAIN')
			sys.exit(POSTPROCESS_ERROR)

	if section_request.status_code == 200:
		return section_request.content
	elif section_request.status_code == 401:
		if os.path.isfile(plex_auth_path):
			os.remove(plex_auth_path)
		if silent_mode:
			print('[WARNING] AUTHORIZATION ERROR. PLEASE RE-RUN SCRIPT TO GENERATE NEW TOKEN. SILENT '
					'FAILURE MODE ACTIVATED')
			sys.exit(POSTPROCESS_SUCCESS)
		else:
			print('[ERROR] AUTHORIZATION ERROR. TOKEN MAY BE INVALID. PLEASE RE-RUN SCRIPT TO GENERATE NEW TOKEN')
			sys.exit(POSTPROCESS_ERROR)


def refresh_advanced(mapping):

	category = None
	plex_section_title = None
	section_key = None
	section_map_list = mapping.split(',')
	for section_map in section_map_list:
		section_map = section_map.strip(' ')
		map_category = section_map.split(':')[0]
		if nzb_cat.lower() == map_category.lower():
			category = map_category
			plex_section_title = section_map.split(':')[1]
			break
	if category is None or plex_section_title is None:
		print('[DEBUG] NZBGET CATEGORY FOR THIS DOWNLOAD IS: {}'.format(nzb_cat))
		print('[ERROR] ERROR DETECTING NZBGET CATEGORY OR PLEX SECTION TITLE. PLEASE MAKE SURE YOUR SECTION '
				'MAPPING IS CORRECT AND TRY AGAIN')
		sys.exit(POSTPROCESS_ERROR)

	root = ET.fromstring(get_plex_sections())
	for directory in root.findall('Directory'):
		section_title = directory.get('title')
		if section_title.lower() == plex_section_title.lower():
			section_key = directory.get('key')
			break
	if section_key is None:
		print('[DEBUG] PLEX SECTION "{}" NOT FOUND ON YOUR SERVER'.format(plex_section_title))
		print('[ERROR] PLEX SECTION NOT FOUND. PLEASE MAKE SURE YOUR SECTION MAPPING IS CORRECT AND TRY AGAIN')
		sys.exit(POSTPROCESS_ERROR)

	refresh_url = 'http://{}/library/sections/{}/refresh'.format(plex_ip, section_key)
	try:
		requests.get(refresh_url, params=params, timeout=10)
	except requests.exceptions.RequestException or OSError:
		requests.session().close()
		if silent_mode:
			print(
				'[WARNING] ERROR UPDATING SECTION {}. SILENT FAILURE MODE ACTIVATED'.format(section_key))
			sys.exit(POSTPROCESS_SUCCESS)
		else:
			print('[ERROR] ERROR UPDATING SECTION {}. CHECK CONNECTION DETAILS AND TRY AGAIN'.format(section_key))
			sys.exit(POSTPROCESS_ERROR)
	print('[DEBUG] REFRESHING PLEX SECTION "{}" MAPPED TO "{}" CATEGORY'.format(plex_section_title, category))
	print('[INFO] TARGETED PLEX UPDATE FOR SECTION {} COMPLETE'.format(section_key))


def refresh_auto(movie_cats, tv_cats):

	movie_cats = movie_cats.replace(' ', '')
	movie_cats_split = movie_cats.split(',')
	tv_cats = tv_cats.replace(' ', '')
	tv_cats_split = tv_cats.split(',')

	root = ET.fromstring(get_plex_sections())
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
				refresh_url = 'http://{}/library/sections/{}/refresh'.format(plex_ip, tv_section)
				try:
					requests.get(refresh_url, params=params, timeout=10)
				except requests.exceptions.RequestException or OSError:
					requests.session().close()
					if silent_mode:
						print('[WARNING] ERROR UPDATING SECTION {}. SILENT FAILURE MODE ACTIVATED'.format(tv_section))
						sys.exit(POSTPROCESS_SUCCESS)
					else:
						print('[ERROR] ERROR UPDATING SECTION {}. CHECK CONNECTION DETAILS AND TRY AGAIN'.format(tv_section))
						sys.exit(POSTPROCESS_ERROR)
				print('[DEBUG] AUTO-DETECTED "{}" CATEGORY. REFRESHING ALL "show" LIBRARIES ON YOUR SERVER'.format(tv_cat))
				print('[INFO] TARGETED PLEX UPDATE FOR SECTION {} COMPLETE'.format(tv_section))
			break

	for movie_cat in movie_cats_split:
		if nzb_cat == movie_cat:
			for movie_section in movie_sections:
				refresh_url = 'http://{}/library/sections/{}/refresh'.format(plex_ip, movie_section)
				try:
					requests.get(refresh_url, params=params, timeout=10)
				except requests.exceptions.RequestException or OSError:
					requests.session().close()
					if silent_mode:
						print('[WARNING] ERROR UPDATING SECTION {}. SILENT FAILURE MODE ACTIVATED'.format(movie_section))
						sys.exit(POSTPROCESS_SUCCESS)
					else:
						print('[ERROR] ERROR UPDATING SECTION {}. CHECK CONNECTION DETAILS AND TRY AGAIN'.format(movie_section))
						sys.exit(POSTPROCESS_ERROR)
				print('[DEBUG] AUTO-DETECTED "{}" CATEGORY. REFRESHING ALL "movie" LIBRARIES ON YOUR SERVER'.format(
					movie_cat))
				print('[INFO] TARGETED PLEX UPDATE FOR SECTION {} COMPLETE'.format(movie_section))
			break


def refresh_custom_sections(raw_plex_sections):

	plex_sections = raw_plex_sections.replace(' ', '')
	plex_sections_split = plex_sections.split(',')

	for plex_section in plex_sections_split:
		refresh_url = 'http://%s/library/sections/%s/refresh' % (plex_ip, plex_section)
		try:
			requests.get(refresh_url, params=params, timeout=10)
		except requests.exceptions.RequestException or OSError:
			requests.session().close()
			if silent_mode:
				print('[WARNING] ERROR UPDATING SECTION %s. SILENT FAILURE MODE ACTIVATED' % plex_section)
				sys.exit(POSTPROCESS_SUCCESS)
			else:
				print('[ERROR] ERROR OPENING URL. CHECK NETWORK CONNECTION, PLEX SERVER IP:PORT, AND SECTION NUMBERS')
				sys.exit(POSTPROCESS_ERROR)
		print('[INFO] TARGETED PLEX UPDATE FOR SECTION %s COMPLETE' % plex_section)


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
		payload = {'id': 1, 'jsonrpc': '2.0', 'method': 'GUI.ShowNotification', 'params': {'title': 'Downloaded', 'message': gui_text}}
		try:
			requests.post(pht_rpc_url, data=json.dumps(payload), headers=headers, timeout=10)
			print('[INFO] NOTIFYPLEX: GUI NOTIFICATION TO PHT INSTANCE SUCCESSFUL')
		except requests.exceptions.RequestException or OSError:
			requests.session().close()
			print('[WARNING] PHT GUI NOTIFICATION FAILED')


command = os.environ.get('NZBCP_COMMAND')
test_mode = command == 'ConnectionTest'
list_sections_mode = command == 'SectionList'

if (command is not None) and (not test_mode) and (not list_sections_mode):
	print('[ERROR] INVALID COMMAND ' + command)
	sys.exit(POSTPROCESS_ERROR)
if list_sections_mode:
	sections_title_list = []
	sections_number_list = []
	sections_type_list = []
	section_count = 0
	required_test_option = 'NZBPO_PLEXIP'

	if required_test_option not in os.environ:
		print('[ERROR] OPTION {} IS MISSING IN CONFIGURATION FILE. PLEASE CHECK SCRIPT SETTINGS'.format(optname[6:]))
		sys.exit(POSTPROCESS_ERROR)

	print('[INFO] GRABBING LIST OF PLEX LIBRARIES AND SECTION NUMBERS')

	root = ET.fromstring(get_plex_sections())
	for directory in root.findall('Directory'):
		sections_title_list.append(directory.get('title'))
		sections_number_list.append(directory.get('key'))
		sections_type_list.append(directory.get('type'))
		section_count += 1
	print('[INFO] YOU HAVE A TOTAL OF {} SECTIONS'.format(section_count))
	for i in range(len(sections_title_list)):
		print('[INFO] SECTION {}: {}, type={}'.format(sections_number_list[i], sections_title_list[i], sections_type_list[i]))
	sys.exit(POSTPROCESS_SUCCESS)

if test_mode:
	required_test_options = ('NZBPO_PLEXUSER', 'NZBPO_PLEXPASS', 'NZBPO_PLEXIP')
	for optname in required_test_options:
		if optname not in os.environ:
			print('[ERROR] OPTION {} IS MISSING IN CONFIGURATION FILE. PLEASE CHECK SCRIPT SETTINGS'.format(optname[6:]))
			sys.exit(POSTPROCESS_ERROR)
	plex_test_ip = os.environ['NZBPO_PLEXIP']

	print('[INFO] TESTING PMS CONNECTION AND AUTHORIZATION')

	test_params = {
		'X-Plex-Token': get_auth_token()
	}
	test_url = 'http://{}/library/sections'.format(plex_test_ip)
	try:
		test_request = requests.get(test_url, params=test_params, timeout=10)
	except requests.exceptions.RequestException or OSError:
		requests.session().close()
		print('[ERROR] ERROR CONNECTING TO PMS. CHECK CONNECTION DETAILS AND RETRY TEST')
		sys.exit(POSTPROCESS_ERROR)
	if test_request.status_code == 200:
		print('[INFO] CONNECTION TEST SUCCESSFUL!')
		sys.exit(POSTPROCESS_SUCCESS)
	else:
		print('[ERROR] AUTHORIZATION ERROR. CHECK CONNECTION DETAILS AND RETRY TEST')
		sys.exit(POSTPROCESS_ERROR)


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
refresh_library = os.environ['NZBPO_REFRESHLIBRARY'] == 'yes'
refresh_mode = os.environ['NZBPO_REFRESHMODE']
silent_mode = os.environ['NZBPO_SILENTFAILURE'] == 'yes'
section_mapping = os.environ['NZBPO_SECTIONMAPPING']

if 'NZBPP_STATUS' not in os.environ:
	print('*** NZBGet post-processing script ***')
	print('This script is supposed to be called from NZBGet v13.0 or later.')
	sys.exit(POSTPROCESS_ERROR)

required_options = ('NZBPO_PLEXIP', 'NZBPO_SILENTFAILURE', 'NZBPO_REFRESHMODE', 'NZBPO_REFRESHLIBRARY', 'NZBPO_DHEADERS', 'NZBPO_GUISHOW')

for optname in required_options:
	if optname not in os.environ:
		print('[ERROR] OPTION {} IS MISSING IN CONFIGURATION FILE. PLEASE CHECK SCRIPT SETTINGS'.format(optname[6:]))
		sys.exit(POSTPROCESS_ERROR)

# Check to see if download was successful
pp_status = os.environ['NZBPP_STATUS'].startswith('SUCCESS/')

if pp_status:

	if gui_show:
		pht_urls = os.environ['NZBPO_CLIENTSIP']
		show_gui_notification(pht_urls)

	if refresh_library:
		raw_plex_section = os.environ['NZBPO_CUSTOMPLEXSECTION']
		movie_cats = os.environ['NZBPO_MOVIESCAT']
		tv_cats = os.environ['NZBPO_TVCAT']

		if refresh_mode == 'Custom':
			refresh_custom_sections(raw_plex_section)
		elif refresh_mode == 'Auto':
			refresh_auto(movie_cats, tv_cats)
		elif refresh_mode == 'Advanced':
			refresh_advanced(section_mapping)
		else:
			refresh_custom_sections(raw_plex_section)
			refresh_auto(movie_cats, tv_cats)

	sys.exit(POSTPROCESS_SUCCESS)

else:
	print('[ERROR] SKIPPING PLEX UPDATE BECAUSE DOWNLOAD FAILED.')
	sys.exit(POSTPROCESS_NONE)
