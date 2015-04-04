# CaCalUploader

Handy script for RWTH Aachen University: It fetches all events of your CampusOffice calendar and uploads them to a
calendar of your choice. As target, only CalDAV calendar is possible, Exchange support is currently under development.
CaCalUploader loads everything from a config file and can so easily be run as cron job.

Requires requests, icalendar, caldav.

Inspired by [Steffen Vogel's cocal script](https://github.com/stv0g/snippets/blob/master/php/campus/cocal.php).
