#!/usr/bin/env python
# coding=utf-8

import caldav
import icalendar
import itertools
import logging
import requests
from adapter import CalDAVAdapter
from datetime import datetime, timedelta
from icalendar.prop import vDatetime

log = logging.getLogger(__name__)


class CampusOfficeAuthorizationError(Exception):
    """The uploader is unable to login into CampusOffice with given matriculation number and password."""

    def __str__(self):
        return 'CampusOffice login failed: Maybe invalid username/password?'


class CampusCalendarUploader(object):
    """
    Fetch all events of the CampusOffice calendar of a given time period and upload them to a CalDAV calendar.
    All already existing events in the CalDAV calendar in this period will be removed.
    """

    # Campus office urls
    _campus_base_url = 'https://www.campus.rwth-aachen.de/office/'
    _campus_login_url = 'views/campus/redirect.asp'
    _campus_cal_url = 'views/calendar/iCalExport.asp?startdt={start:%d.%m.%Y}&enddt={end:%d.%m.%Y} 23:59:59'
    _campus_logout_url = 'system/login/logoff.asp'

    def __init__(self, mat_number, campus_pass, upload_calendar, start_time=None, end_time=None):
        """
        Initialize object with given values. The default time period if none given is 1 week in the past from today
        to 27 weeks in the future.
        :param mat_number: Matriculation number used for the CampusOffice.
        :param campus_pass: Password for CampusOffice.
        :param upload_calendar: Calendar adapter to upload events to.
        :param start_time: Start date of time period. Default: 1 week in the past from today.
        :param end_time: Start date of time period. Default: 27 weeks in the future from today.
        :raise ValueError: Raised if only one time boundary is provided.
        """
        # Set default values for time period
        today = datetime.today()
        self._start_time = today + timedelta(weeks=-1)
        self._end_time = today + timedelta(weeks=27)

        # Save parameters
        self.matriculation_number = mat_number
        self.campus_password = campus_pass
        self.upload_calendar = upload_calendar

        # If given save time period
        if start_time is not None and end_time is not None:
            self.start_time = start_time
            self.end_time = end_time
        # Prevent misuse with only one time period boundary
        elif (start_time is None) != (end_time is None):
            raise ValueError('Can not upload calendar with only one time period boundary')

    @property
    def start_time(self):
        return self._start_time

    @start_time.setter
    def start_time(self, start):
        # Check for non-existing end
        if self.end_time is None:
            self._end_time = start
        # Check for valid time period
        elif self.end_time < start:
            raise ValueError('Start of time period is after end')

        self._start_time = start

    @property
    def end_time(self):
        return self._end_time

    @end_time.setter
    def end_time(self, end):
        # Check for non-existing start
        if self.start_time is None:
            self._start_time = end
        # Check for valid time period
        elif self.start_time > end:
            raise ValueError('End of time period is before start')

        self._end_time = end

    def upload(self):
        """
        Perform the job of the class. Fetch the CampusOffice calendar and upload all events to the give CALDav calendar.
        :raise requests.RequestException: Raised if connection to CampusOffice failed.
        :raise CampusOfficeAuthorizationError: Raised if CampusOffice login failed.
        :raise caldav.error.AuthorizationError: Raised if caldav username or password are incorrect.
        :raise caldav.error.NotFoundError: Raised if caldav calendar could not be found.
        :raise caldav.error.ReportError: Raised if list of existing events in time period could not be loaded from
            caldav calendar.
        :raise caldav.error.DeleteError: Raised if removing of already existing event in caldav calendar failed.
        :raise caldav.error.PutError: Raised if upload of an event failed.
        """
        # Retrieve current calendar
        source_cal = self._retrieve_source_calendar()
        # Remove all components which are no events
        source_events = filter(lambda x: isinstance(x, icalendar.Event), source_cal.subcomponents)

        # Connect upload calendar
        log.info('Search for caldav calendar')
        self.upload_calendar.connect()

        # Upload all events to calendar
        self._upload_events(source_events)

    def _retrieve_source_calendar(self):
        """
        Retrieve all events entered in CampusOffice.
        :return: :class:`icalendar.Calendar` calendar object with all events from CampusOffice.
        :raise requests.RequestException: Raised if connection to CampusOffice failed.
        :raise CampusOfficeAuthorizationError: Raised if CampusOffice login failed.
        """
        cls = CampusCalendarUploader
        # Create session which cares about cookies
        session = requests.Session()

        # Fetch base page for session cookies
        log.info('Fetch base page for session cookie')
        req = session.get(cls._campus_base_url)
        req.raise_for_status()

        # Log in and validating session cookies
        log.info('Validate session by logging in')
        values = {'u': self.matriculation_number,
                  'p': self.campus_password}
        req = session.post(cls._campus_base_url + cls._campus_login_url, data=values)
        req.raise_for_status()
        if 'loginfailed' in req.history[0].headers['location']:
            raise CampusOfficeAuthorizationError()
        
        # Retrieve calendar
        log.info('Retrieve calendar')
        req = session.get(cls._campus_base_url + cls._campus_cal_url.format(start=self.start_time, end=self.end_time))
        req.raise_for_status()

        # Log out
        log.info('Invalidating session by logging out')
        session.get(cls._campus_base_url + cls._campus_logout_url)

        # Parse calendar with forced utf-8
        log.info('Parse calendar')
        req.encoding = 'utf-8'
        return icalendar.Calendar.from_ical(req.text)

    def _upload_events(self, events):
        """
        Upload all given events to caldav calendar and remove all other events in time period.
        :raise caldav.error.ReportError: Raised if list of existing events in time period could not be loaded.
        :raise caldav.error.DeleteError: Raised if removing of already existing event failed.
        :raise caldav.error.PutError: Raised if upload of an event failed.
        """
        # Filter events which where already uploaded
        log.info('Fetch all existing events')
        events = list(events)
        old_event_ids = self.upload_calendar.retrieve_event(self.start_time, self.end_time)
        n = 0
        for (new, old_id) in itertools.product(events, old_event_ids):
            if new['uid'] == old_id:
                events.remove(new)
                old_event_ids.remove(old_id)
                n += 1
        if n > 0:
            log.info('{n} event(s) where already uploaded'.format(n=n))

        # Remove only deprecated events
        n = len(old_event_ids)
        if n > 0:
            log.info('Delete {n} deprecated event(s) in given time period'.format(n=n))
        else:
            log.info('No deprecated event(s) found in calendar')

        for i, uid in enumerate(old_event_ids):
            log.info('Delete event {index}/{num}'.format(index=i+1, num=n))
            self.upload_calendar.delete_event(uid)

        # Upload all events
        n = len(events)
        if n > 0:
            log.info('Upload all new events')
        else:
            log.info('No new events found')

        for i, ev in enumerate(events):
            log.info('Upload event {index}/{num}'.format(index=i+1, num=n))
            uid = ev['uid']
            title = ev['summary']
            start = vDatetime.from_ical(ev['dtstart'].to_ical(), 'Europe/Berlin')
            end = vDatetime.from_ical(ev['dtend'].to_ical(), 'Europe/Berlin')
            location = ev['location']
            self.upload_calendar.add_event(uid, title, start, end, location)
        
        log.info('Uploaded all changes')


if __name__ == '__main__':
    # The script will try to load everything from a config file with following structure:
    # [CampusOffice]
    # mat=<matriculation number>
    # pass=<password>
    #
    # [Adapter]
    # target=caldav
    #
    # [CalDAV]
    # url=<calendar url>
    # username=<calendar username>
    # password=<password>
    #
    # and optional:
    # [Period]
    # start=<year-month-day>
    # end=<year-month-day>

    import sys
    import configparser

    # Set up logger
    logging.basicConfig(format='%(asctime)s %(levelname)s: %(name)s: %(message)s', level=logging.INFO,
                        datefmt='%Y-%m-%d %H:%M:%S')
    log = logging.getLogger('cacaluploader')

    # Parse command line
    if len(sys.argv) != 2:
        log.error('Error: Incorrect use!')
        log.info(' cacaluploader.py <config-file>')
        exit()
    config_file = sys.argv[1]

    try:
        # Parse config file
        config = configparser.ConfigParser()
        config.read(config_file)
        mat_number = config.get('CampusOffice', 'mat')
        campus_pass = config.get('CampusOffice', 'pass')

        target = config.get('Adapter', 'target')

        if target == 'caldav':
            url = config.get('CalDAV', 'url')
            username = config.get('CalDAV', 'username')
            password = config.get('CalDAV', 'password')
            adapter = CalDAVAdapter(url, username, password)
        else:
            raise RuntimeError('Unknown adapter!')

        if config.has_section('Period'):
            start_time = datetime.strptime(config.get('Period', 'start'), '%Y-%m-%d')
            end_time = datetime.strptime(config.get('Period', 'end'), '%Y-%m-%d')
        else:
            start_time = None
            end_time = None

        # Start upload

        uploader = CampusCalendarUploader(mat_number, campus_pass, adapter, start_time, end_time)
        uploader.upload()
    except configparser.NoOptionError as e:
        log.error('Could not load config from file: %s', e)
    except (requests.RequestException, CampusOfficeAuthorizationError) as e:
        log.error('Could not retrieve CampusOffice calendar: %s', e)
    except caldav.error.AuthorizationError as e:
        log.error('Could not access CalDAV calendar: Authorization failed')
    except caldav.error.NotFoundError as e:
        log.error('Could not find CalDAV calendar')
    except caldav.error.ReportError as e:
        log.error('Could not retrieve list of already existing events in CalDAV calendar')
    except caldav.error.DeleteError as e:
        log.error('Could not remove already existing event in CalDAV calendar')
    except caldav.error.PutError as e:
        log.error('Could not upload new event to CalDAV calendar')
    # Maybe catch many other things too :(
    except ValueError as e:
        log.error('Could not parse time period: %s', e)
