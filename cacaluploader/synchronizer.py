import itertools
import logging

from .source_adapters import CalendarSourceAdapter
from .upload_adapters import CalendarUploadAdapter

log = logging.getLogger(__name__)


class CampusCalendarUploader(object):
    """
    Fetch all events of the CampusOffice calendar of a given time period and upload them to a CalDAV calendar.
    All already existing events in the CalDAV calendar in this period will be removed.
    """

    def __init__(self, source_adapter: CalendarSourceAdapter, upload_calendar: CalendarUploadAdapter):
        """
        Initialize object with given values. The default time period if none given is 1 week in the past from today
        to 27 weeks in the future.
        :param source_adapter: Source providing events
        :param upload_calendar: Calendar adapter to upload events to.
        """
        # Save parameters
        self.source_adapter = source_adapter
        self.upload_calendar = upload_calendar

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
        events = self.source_adapter.events

        # Connect upload calendar
        log.info('Search for upload calendar')
        self.upload_calendar.connect()

        # Filter events which where already uploaded
        log.info('Fetch all existing events')
        old_event_ids = []
        start_date = self.source_adapter.start_time
        end_date = self.source_adapter.end_time
        if start_date is not None and end_date is not None:
            old_event_ids = self.upload_calendar.retrieve_event_ids(start_date, end_date)

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
            self.upload_calendar.add_event(ev)
        
        log.info('Uploaded all changes')
