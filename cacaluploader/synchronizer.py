import itertools
import logging
from datetime import datetime, timedelta

from .event import Event
from .source_adapters import CampusCalenderAdapter

log = logging.getLogger(__name__)


class CampusCalendarUploader(object):
    """
    Fetch all events of the CampusOffice calendar of a given time period and upload them to a CalDAV calendar.
    All already existing events in the CalDAV calendar in this period will be removed.
    """

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
        campus_cal = CampusCalenderAdapter(self.matriculation_number, self.campus_password, self.start_time, self.end_time)
        events = campus_cal.events

        # Connect upload calendar
        log.info('Search for upload calendar')
        self.upload_calendar.connect()

        # Upload all events to calendar
        self._upload_events(events)

    def _upload_events(self, events):
        """
        Upload all given events to caldav calendar and remove all other events in time period.
        :param list[Event] events: Events to upload.
        :raise caldav.error.ReportError: Raised if list of existing events in time period could not be loaded.
        :raise caldav.error.DeleteError: Raised if removing of already existing event failed.
        :raise caldav.error.PutError: Raised if upload of an event failed.
        """
        # Filter events which where already uploaded
        log.info('Fetch all existing events')
        old_event_ids = self.upload_calendar.retrieve_event_ids(self.start_time, self.end_time)
        n = 0
        for (new, old_id) in itertools.product(events, old_event_ids):
            if new.uid == old_id:
                events.remove(new)
                old_event_ids.remove(old_id)
                n += 1
        if n > 0:
            log.info('{n} event(s) were already uploaded'.format(n=n))

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
            self.upload_calendar.add_event(ev.uid, ev.title, ev.start_time, ev.end_time, ev.location)
        
        log.info('Uploaded all changes')
