import icalendar
from datetime import datetime


class Event(object):
    """Class abstracting events from different kind of sources."""

    def __init__(self, uid: str, cal_uid: str, title: str, start_time: datetime, end_time: datetime, location: str):
        """
        Initialize object with given values.
        :param uid: Event's uid, should be unique regarding the calender_uid.
        :param cal_uid: Calendar's uid where the events originates from.
        :param title: Main title of event.
        :param start_time: Event's starting time.
        :param end_time: Event's ending time.
        :param location: Location where the event takes place.
        """
        self._uid = uid
        self._calender_uid = cal_uid
        self._title = title
        self._start_time = start_time
        self._end_time = end_time
        self._location = location

    @classmethod
    def from_ical_event(cls, event: icalendar.Event, cal_uid: str=None):
        """
        Construct object from an iCalendar event.
        :param cal_uid: Unique id of calendar the event belongs to.
        :param event: Event object to parse.
        :rtype: Event
        """
        uid = str(event['uid'])
        title = str(event['summary'])
        location = str(event['location'])

        # Doing time conversion to keep timezone
        start = event['dtstart'].dt
        end = event['dtend'].dt

        return Event(uid, cal_uid, title, start, end, location)

    @property
    def uid(self) -> str:
        """
        :return Uid which is unique regarding the calender_uid.
        """
        return self._uid

    @property
    def calender_uid(self) -> str:
        """
        :return Uid of the calendar the events originates from.
        """
        return self._calender_uid

    @property
    def title(self) -> str:
        """
        :return Main title of the event.
        """
        return self._title

    @property
    def start_time(self) -> datetime:
        """
        :return Starting time
        """
        return self._start_time

    @property
    def end_time(self) -> datetime:
        """
        :return Ending time
        """
        return self._end_time

    @property
    def location(self) -> str:
        """
        :return Location where the event takes place
        """
        return self._location
