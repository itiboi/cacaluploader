import itertools
import logging

from .source_adapters import CalendarSourceAdapter
from .upload_adapters import CalendarUploadAdapter

log = logging.getLogger(__name__)


class CalendarSynchronizer(object):
    """
    Fetch all events of a source calendar and upload them to a target calendar.
    All already existing events of the source calendar in this period will be removed.
    """

    def __init__(self, source_adapter: CalendarSourceAdapter, upload_calendar: CalendarUploadAdapter):
        """
        Initialize object with given values.
        :param source_adapter: Source providing events
        :param upload_calendar: Calendar adapter to upload events to.
        """
        # Save parameters
        self.source_adapter = source_adapter
        self.upload_calendar = upload_calendar

    def upload(self):
        """
        Perform the job of the class. Fetch the source calendar and upload all events to the given upload calendar.
        :raise requests.RequestException: Raised if connection to calendar failed.
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
        log.info('Connect to upload calendar')
        self.upload_calendar.connect()

        # Filter events which where already uploaded
        log.info('Fetch all existing events')
        old_events = []
        start_date = self.source_adapter.start_time
        end_date = self.source_adapter.end_time
        if start_date is not None and end_date is not None:
            old_events = self.upload_calendar.retrieve_event_ids(start_date, end_date)

        n = 0
        old_events = list(filter(lambda ids: ids[0] == self.source_adapter.uid, old_events))
        for (new, (cal_id, old_id)) in itertools.product(events, old_events):
            if new.calender_uid == cal_id and new.uid == old_id:
                events.remove(new)
                old_events.remove((cal_id, old_id))
                n += 1
        if n > 0:
            log.info('{n} event(s) were already uploaded'.format(n=n))

        # Remove only deprecated events
        n = len(old_events)
        if n > 0:
            log.info('Delete {n} deprecated event(s) in given time period'.format(n=n))
        else:
            log.info('No deprecated event(s) found in calendar')

        for i, (cal_id, ev_id) in enumerate(old_events):
            log.info('Delete event {index}/{num}'.format(index=i+1, num=n))
            self.upload_calendar.delete_event(cal_id, ev_id)

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
