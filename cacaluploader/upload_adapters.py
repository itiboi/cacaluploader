import caldav
import icalendar
import pyexchange
import re


class CalendarUploadAdapter(object):
    """Interface definition to allow interaction with different calendar providers for uploading events."""

    def connect(self):
        """Establish connection to upload calendar."""
        raise NotImplementedError()

    def retrieve_event_ids(self, start_time, end_time):
        """
        Retrieve uid of all events in time period.
        :param start_time: Start date of time period.
        :param end_time: Start date of time period.
        :return: List with ids of all events in time period.
        """
        raise NotImplementedError()

    def delete_event(self, uid):
        """
        Remove event with given uid from calendar.
        :param uid: Id of event to delete.
        """
        raise NotImplementedError()

    def add_event(self, uid, title, start_time, end_time, location):
        """
        Create a new event with given values in calendar.
        :param uid: Id of event for identification.
        :param title: Main title of event.
        :param start_time: Event starting time.
        :param end_time: Event end time.
        :param location: Event room/location.
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

    def retrieve_event_ids(self, start_time, end_time):
        """
        :raise caldav.error.ReportError: Raised if list of existing events in time period could not be loaded.
        """
        self.events = self.calendar.date_search(start_time, end_time)
        return list(map(lambda x: x.instance.vevent.uid.value, self.events))

    def delete_event(self, uid):
        """
        :raise caldav.error.DeleteError: Raised if removing of already existing event failed.
        """
        event = filter(lambda x: x.instance.vevent.uid.value == uid, self.events)
        for e in event:
            e.delete()

    def add_event(self, uid, title, start_time, end_time, location):
        """
        :raise caldav.error.PutError: Raised if upload of an event failed.
        """
        # Create iCal representation of event
        event = icalendar.Event()
        event.add('uid', uid)
        event.add('summary', title)
        event.add('dtstart', start_time)
        event.add('dtend', end_time)
        event.add('location', location)
        event_cal = icalendar.Calendar()
        event_cal.add_component(event)

        # Add it
        self.calendar.add_event(event_cal.to_ical())


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

    def retrieve_event_ids(self, start_time, end_time):
        """
        :raise
        """
        self.events = self.calendar.list_events(start=start_time, end=end_time, details=True).events
        return list(map(lambda x: ExchangeUploadAdapter._tag_re.sub('', x.body), self.events))

    def delete_event(self, uid):
        """
        :raise
        """
        events = filter(lambda x: ExchangeUploadAdapter._tag_re.sub('', x.body) == uid, self.events)
        for e in events:
            e.cancel()

    def add_event(self, uid, title, start_time, end_time, location):
        """
        :raise
        """
        event = self.calendar.event()
        event.subject = title
        event.start = start_time
        event.end = end_time
        event.location = location
        event.html_body = uid
        event.create()
