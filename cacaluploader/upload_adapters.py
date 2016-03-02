import caldav
import icalendar
import pyexchange
import pytz
import re

from datetime import datetime

from .event import Event


class CalendarUploadAdapter(object):
    """Interface definition to allow interaction with different calendar providers for uploading events."""

    _separator = '-|-'

    def connect(self):
        """Establish connection to upload calendar."""
        raise NotImplementedError()

    def retrieve_event_ids(self, start_time: datetime, end_time: datetime):
        """
        Retrieve calendar uids and uids of all events in time period.
        :param start_time: Start date of time period.
        :param end_time: Start date of time period.
        :return: List of all events in time period in format (calendar uid, event uid). Calendar uid will be None
                 if unknown.
        :rtype: list[(str, str)]
        """
        raise NotImplementedError()

    def delete_event(self, cal_uid: str, ev_uid: str):
        """
        Remove given event from calendar.
        :param cal_uid: Calender id of event to delete. Can be None.
        :param ev_uid: Event id of calendar to remove.
        """
        raise NotImplementedError()

    def add_event(self, event: Event):
        """
        Create a new event with given values in calendar.
        :param event: Event to add
        """
        raise NotImplementedError()


class CalDAVUploadAdapter(CalendarUploadAdapter):
    """Implements interaction with a CalDAV calendar provider."""

    def __init__(self, url, username, password):
        """
        Initialize object with given values.
        :param url: URL of CalDAV calendar to adapt to.
        :param username: User of CalDAV calendar.
        :param password: Password for CalDAV calendar.
        """
        self.url = url
        self.username = username
        self.password = password
        self.calendar = None
        self.events = None

    def connect(self):
        """
        :raise caldav.error.AuthorizationError: Raised if username or password are incorrect.
        :raise caldav.error.NotFoundError: Raised if calendar could not be found.
        """
        client = caldav.DAVClient(self.url, username=self.username, password=self.password)
        principal = caldav.Principal(client)

        # Search for given calendar
        for c in principal.calendars():
            url = str(c.url)
            if self.url == url:
                self.calendar = c
                return

        # No calendar found (should normally not happen; principal should have raised error)
        raise caldav.error.NotFoundError('Could not find calendar with given url')

    def retrieve_event_ids(self, start_time: datetime, end_time: datetime):
        """
        :raise caldav.error.ReportError: Raised if list of existing events in time period could not be loaded.
        """
        self.events = self.calendar.date_search(start_time, end_time)

        def extractor(event):
            raw_id = event.instance.vevent.uid.value
            splitted_id = raw_id.split(CalendarUploadAdapter._separator)
            if len(splitted_id) == 1:
                splitted_id.insert(0, None)
            return tuple(splitted_id)

        return list(map(extractor, self.events))

    def delete_event(self, cal_uid: str, ev_uid: str):
        """
        :raise caldav.error.DeleteError: Raised if removing of already existing event failed.
        """
        # Compute real event id
        uid = ev_uid
        if cal_uid is not None:
            uid = cal_uid + CalendarUploadAdapter._separator + uid

        event = filter(lambda x: x.instance.vevent.uid.value == uid, self.events)
        for e in event:
            e.delete()

    def add_event(self, event: Event):
        """
        :raise caldav.error.PutError: Raised if upload of an event failed.
        """
        # Create iCal representation of event
        new_event = icalendar.Event()
        new_event.add('uid', event.calender_uid + CalendarUploadAdapter._separator + event.uid)
        new_event.add('summary', event.title)
        new_event.add('location', event.location)

        # Convert to UTC to avoid DST hassles
        utc = pytz.timezone('UTC')
        new_event.add('dtstart', event.start_time.astimezone(utc))
        new_event.add('dtend', event.end_time.astimezone(utc))

        event_cal = icalendar.Calendar()
        event_cal.add_component(new_event)

        # Add it
        self.calendar.add_event(event_cal.to_ical())


# TODO: Complete documentation
class ExchangeUploadAdapter(CalendarUploadAdapter):
    """Implements interaction with an Exchange calendar."""

    _tag_re = re.compile(r'(<!--.*?-->|<[^>]*>|\n|\r)')

    def __init__(self, ews_url, username, password, calendar_id=None):
        """

        :param ews_url:
        :param username:
        :param password:
        :param calendar_id:
        :return:
        """
        self.connection = pyexchange.ExchangeNTLMAuthConnection(url=ews_url, username=username, password=password)
        self.calendar_name = calendar_id
        self.calendar = None
        self.events = None

    def connect(self):
        """
        :raise
        """
        service = pyexchange.Exchange2010Service(self.connection)
        if self.calendar_name is not None:
            # Find calendar with given name
            folders = service.folder().find_folder(parent_id='calendar')
            calendar_id = None
            for folder in folders:
                if folder.display_name == self.calendar_name:
                    calendar_id = folder.id

            # Check if calendar was not found
            if calendar_id is None:
                raise caldav.error.NotFoundError('Could not find calendar with given url')

            self.calendar = service.calendar(id=calendar_id)
        else:
            self.calendar = service.calendar()

    def retrieve_event_ids(self, start_time: datetime, end_time: datetime):
        """
        :raise
        """
        self.events = self.calendar.list_events(start=start_time, end=end_time, details=True).events
        return list(map(lambda x: ExchangeUploadAdapter._tag_re.sub('', x.body), self.events))

    def delete_event(self, cal_uid: str, ev_uid: str):
        """
        :raise
        """
        events = filter(lambda x: ExchangeUploadAdapter._tag_re.sub('', x.body) == uid, self.events)
        for e in events:
            e.cancel()

    def add_event(self, event: Event):
        """
        :raise
        """
        new_event = self.calendar.event()
        new_event.subject = event.title
        new_event.start = event.start_time
        new_event.end = event.end_time
        new_event.location = event.location
        new_event.html_body = event.uid
        new_event.create()
