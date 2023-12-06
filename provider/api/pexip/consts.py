import enum


class GuestLayout(enum.Enum):

    one_main_zero_pips = 'Full-screen main speaker only'
    one_main_seven_pips = 'Large main speaker and up to 7 other participants'
    one_main_twentyone_pips = 'Main speaker and up to 21 other participants'
    two_mains_twentyone_pips = 'Two main speakers and up to 21 other participants'
    four_mains_zero_pips = 'Up to four main speakers, with no thumbnails'


class HostLayout(enum.Enum):
    one_main_zero_pips = 'Full-screen main speaker only'
    one_main_seven_pips = 'Large main speaker and up to 7 other participants'
    one_main_twentyone_pips = 'Main speaker and up to 21 other participants'
    two_mains_twentyone_pips = 'Two main speakers and up to 21 other participants'
    four_mains_zero_pips = 'Up to four main speakers, with no thumbnails'
    five_mains_seven_pips = (
        'Adaptive Composition layout (does not apply to service_type of lecture)'
    )
