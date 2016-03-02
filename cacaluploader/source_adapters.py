import hashlib
import icalendar
import requests
from datetime import datetime, timedelta
from logging import getLogger

from .event import Event

log = getLogger(__name__)


class CalendarSourceAdapter(object):
    """Interface definition to allow interaction with different calendar providers for fetching events."""

    def __init__(self, uid: str):
        """
        :param uid: Unique calendar id.
        """
        # Initialize event list
        self._uid = uid
        self._events = None

    def retrieve_events(self):
        """
        Establish connection to calendar and fetches the events. Will be automatically called when accessing events
        without a previous call.
        """
        raise NotImplementedError()

    @property
    def uid(self) -> str:
        """
        :return: Unique calendar id.
        """
        return self._uid

    @property
    def events(self):
        """
        :return: All events provided by the calender. Can be empty.
        :rtype: list[Event]
        """
        # Fetch events if not done up to now.
        if self._events is None:
            self.retrieve_events()

        return self._events

    @property
    def start_time(self) -> datetime:
        """
        :return: Starting time of the first event provided. None if no event available.
        """
        first = None
        for e in self.events:
            if first is None or e.start_time < first:
                first = e.start_time

        return first

    @property
    def end_time(self) -> datetime:
        """
        :return: Ending time of the last event provided. None if no event available.
        """
        last = None
        for e in self.events:
            if last is None or last < e.end_time:
                last = e.end_time

        return last


class CampusOfficeAuthorizationError(Exception):
    """The adapter is unable to login into CampusOffice with given matriculation number and password."""

    def __str__(self):
        return 'CampusOffice login failed: Maybe invalid username/password?'


class CampusCalenderAdapter(CalendarSourceAdapter):
    """Adapter to fetch all events of the CampusOffice calendar of a given time period."""

    # Campus office urls
    _campus_base_url = 'https://www.campus.rwth-aachen.de/office/'
    _campus_login_url = 'views/campus/redirect.asp'
    _campus_cal_url = 'views/calendar/iCalExport.asp?startdt={start:%d.%m.%Y}&enddt={end:%d.%m.%Y} 23:59:59'
    _campus_logout_url = 'system/login/logoff.asp'

    def __init__(self, mat_number: str, campus_pass: str, start_time: datetime=None, end_time: datetime=None,
                 uid: str=None):
        """
        Initialize object with given values. The default time period if none given is 1 week in the past from today
        to 27 weeks in the future.
        :param str mat_number: Matriculation number used for the CampusOffice.
        :param str campus_pass: Password for CampusOffice.
        :param datetime.datetime start_time: Start date of time period. Default: 1 week in the past from today.
        :param datetime.datetime end_time: Start date of time period. Default: 27 weeks in the future from today.
        :param uid: Unique calendar id. Will use hash of matriculation number if omitted.
        """
        if uid is None:
            uid = hashlib.sha1(mat_number.encode('utf')).digest()
        super().__init__(uid=uid)

        # Set default values for time period
        today = datetime.today()
        self._start_time = today + timedelta(weeks=-1)
        self._end_time = today + timedelta(weeks=27)

        # Save parameters
        self.matriculation_number = mat_number
        self.campus_password = campus_pass

        # If given save time period
        if start_time is not None and end_time is not None:
            self._start_time = start_time
            self._end_time = end_time
        # Prevent misuse with only one time period boundary
        elif (start_time is None) != (end_time is None):
            raise ValueError('Can not retrieve calendar with only one time period boundary')

    def retrieve_events(self):
        """
        :raise requests.RequestException: Raised if connection to CampusOffice failed.
        :raise CampusOfficeAuthorizationError: Raised if CampusOffice login failed.
        """
        cls = CampusCalenderAdapter
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
        req = session.get(cls._campus_base_url + cls._campus_cal_url.format(start=self._start_time, end=self._end_time))
        req.raise_for_status()

        # Log out
        log.info('Invalidating session by logging out')
        session.get(cls._campus_base_url + cls._campus_logout_url)

        # Parse calendar with forced utf-8
        log.info('Parse calendar')
        req.encoding = 'utf-8'
        calendar = icalendar.Calendar.from_ical(req.text)

        # Remove all components which are no events
        events = filter(lambda e: isinstance(e, icalendar.Event), calendar.subcomponents)
        self._events = list(map(lambda e: Event.from_ical_event(e, self.uid), events))

    @property
    def start_time(self) -> datetime:
        return self._start_time

    @property
    def end_time(self) -> datetime:
        return self._end_time


class ICalendarAdapter(CalendarSourceAdapter):
    """Adapter to fetch events from a simple iCal calendar url."""

    def __init__(self, url: str, uid: str=None):
        """
        Initialize object with given values.
        :param url: Url to calendar in iCalendar format.
        :param uid: Unique calendar id. Will use a hash of the url if omitted.
        """
        if uid is None:
            uid = hashlib.sha1(url.encode('utf')).digest()
        super().__init__(uid=uid)

        self._url = url

    def retrieve_events(self):
        """
        :raise requests.RequestException: Raised if connection to calendar failed.
        """
        # Retrieve calendar
        log.info('Retrieve calendar')
        req = requests.get(self._url)
        req.raise_for_status()

        # Parse calendar with forced utf-8
        log.info('Parse calendar')
        req.encoding = 'utf-8'
        calendar = icalendar.Calendar.from_ical(req.text)

        # Remove all components which are no events
        events = filter(lambda e: isinstance(e, icalendar.Event), calendar.subcomponents)
        self._events = list(map(lambda e: Event.from_ical_event(e, self.uid), events))
