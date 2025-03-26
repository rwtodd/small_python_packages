import datetime
import calendar
import random

class DiscordianDate:
    """Represents a Discordian date, providing properties for date components and a method to format strings."""
    
    # Static constants for seasons, weekdays, holy days, and exclamations
    _SEASONS = ["Chaos", "Chs", "Discord", "Dsc", "Confusion", "Cfn", "Bureaucracy", "Bcy", "The Aftermath", "Afm"]
    _DAYS = ["Sweetmorn", "SM", "Boomtime", "BT", "Pungenday", "PD", "Prickle-Prickle", "PP", "Setting Orange", "SO"]
    _HOLYDAY_5 = ["Mungday", "Mojoday", "Syaday", "Zaraday", "Maladay"]
    _HOLYDAY_50 = ["Chaoflux", "Discoflux", "Confuflux", "Bureflux", "Afflux"]
    _EXCLAIM = [
        "Hail Eris!", "All Hail Discordia!", "Kallisti!", "Fnord.", "Or not.",
        "Wibble.", "Pzat!", "P'tang!", "Frink!", "Slack!", "Praise \"Bob\"!", "Or kill me.",
        "Grudnuk demand sustenance!", "Keep the Lasagna flying!",
        "You are what you see.", "Or is it?", "This statement is false.",
        "Lies and slander, sire!", "Hee hee hee!", "Hail Eris, Hack Python!"
    ]

    def __repr__(self) -> str:
        return f'DiscordianDate({self._gdate!r})'

    def __str__(self) -> str:
        return self.format('%d-%b-%Y')

    def __format__(self, fmt_str: str) -> str:
        if len(fmt_str) == 0:
            return str(self)
        return self.format(fmt_str)

    def __init__(self, date=None):
        """
        Initialize a DiscordianDate with a datetime.date object.
        If no date is provided, use the current date.
        
        Args:
            date (datetime.date, optional): The Gregorian date. Defaults to today's date.
        """
        self._gdate = date if date is not None else datetime.date.today()
        is_leap = calendar.isleap(self._gdate.year)
        self._is_tibs = is_leap and self._gdate.month == 2 and self._gdate.day == 29
        day_of_year = self._gdate.timetuple().tm_yday
        # Adjust day of year: -1 normally, -2 after February in leap years to skip St. Tib's Day
        self._adjusted_yday = day_of_year - (2 if is_leap and self._gdate.month > 2 else 1)
        # Season day is 1-73, None for St. Tib's Day
        self._season_day = (self._adjusted_yday % 73) + 1 if not self._is_tibs else None

    @property
    def year(self):
        """The Discordian year (Gregorian year + 1166)."""
        return self._gdate.year + 1166

    @property
    def day_of_season(self):
        """The day of the Discordian season (1-73), or None for St. Tib's Day."""
        return self._season_day

    @property
    def is_tibs(self):
        """True if the date is St. Tib's Day."""
        return self._is_tibs

    @property
    def season(self):
        """The full season name, or 'St. Tib's Day' if applicable."""
        return "St. Tib's Day" if self._is_tibs else self._SEASONS[2 * (self._adjusted_yday // 73)]

    @property
    def short_season(self):
        """The abbreviated season name, or 'St. Tib's Day' if applicable."""
        return "St. Tib's Day" if self._is_tibs else self._SEASONS[2 * (self._adjusted_yday // 73) + 1]

    @property
    def weekday(self):
        """The full weekday name, or 'St. Tib's Day' if applicable."""
        return "St. Tib's Day" if self._is_tibs else self._DAYS[2 * (self._adjusted_yday % 5)]

    @property
    def short_weekday(self):
        """The abbreviated weekday name, or 'St. Tib's Day' if applicable."""
        return "St. Tib's Day" if self._is_tibs else self._DAYS[2 * (self._adjusted_yday % 5) + 1]

    @property
    def is_holy_day(self):
        """True if the date is a holy day (day 5 or 50 of the season)."""
        return self._season_day in (5, 50)

    @property
    def holy_day_name(self):
        """The holy day name if applicable, else an empty string."""
        if self._season_day == 5:
            return self._HOLYDAY_5[self._adjusted_yday // 73]
        elif self._season_day == 50:
            return self._HOLYDAY_50[self._adjusted_yday // 73]
        return ""

    @property
    def days_til_xday(self):
        """The number of days until X-Day (July 5, 8661)."""
        xday = datetime.date(8661, 7, 5)
        return (xday - self._gdate).days

    @staticmethod
    def _ordinal_suffix(number):
        """Return the ordinal suffix for a number (e.g., 'st', 'nd', 'rd', 'th')."""
        if 10 <= number % 100 <= 20:
            return "th"
        return {1: "st", 2: "nd", 3: "rd"}.get(number % 10, "th")

    def format(self, fstr):
        """
        Format the Discordian date according to the given format string.
        Supports ddate-compatible format codes.
        
        Args:
            fstr (str): The format string with ddate codes.
        
        Returns:
            str: The formatted Discordian date string.
        """
        result = []
        idx = 0
        last = len(fstr)
        while idx < last:
            if fstr[idx] == '%':
                idx += 1
                if idx >= last:
                    break
                cmd = fstr[idx]
                match cmd:
                    case '%':
                        result.append('%')
                    case 'A':
                        result.append(self.weekday)
                    case 'a':
                        result.append(self.short_weekday)
                    case 'B':
                        result.append(self.season)
                    case 'b':
                        result.append(self.short_season)
                    case 'd':
                        if self.day_of_season is not None:
                            result.append(str(self.day_of_season))
                    case 'e':
                        if self.day_of_season is not None:
                            result.append(str(self.day_of_season) + self._ordinal_suffix(self.day_of_season))
                    case 'H':
                        result.append(self.holy_day_name)
                    case 'n':
                        result.append('\n')
                    case 't':
                        result.append('\t')
                    case 'X':
                        result.append(f"{self.days_til_xday:,}")
                    case 'Y':
                        result.append(str(self.year))
                    case '.':
                        result.append(random.choice(self._EXCLAIM))
                    case '}':
                        pass  # no-op
                    case 'N':
                        if not self.is_holy_day:
                            idx = last  # Skip rest unless holy day
                    case '{':
                        if self.is_tibs:
                            result.append("St. Tib's Day")
                            pos = fstr.find('%}', idx)
                            if pos != -1:
                                idx = pos + 1  # Move to '}', loop will advance past
                            else:
                                idx = last  # No closing '%}', skip to end
                        # Else, continue processing normally
                    case _:
                        result.append(cmd)  # Unknown command, append as is
                idx += 1  # Move past the command character
            else:
                result.append(fstr[idx])
                idx += 1
        return ''.join(result)

# Example usage
if __name__ == "__main__":
    # Current date
    ddate = DiscordianDate()
    print(ddate.format("Today is %A, %B %d, %Y. %{ %N%nCelebrate %H!%}"))
    
    # St. Tib's Day
    ddate = DiscordianDate(datetime.date(2024, 2, 29))
    print(ddate.format("Today is %A, %B %d, %Y. %{ %N%nCelebrate %H!%}"))
    
    # Holy day example (January 5, 2023 - Mungday)
    ddate = DiscordianDate(datetime.date(2023, 1, 5))
    print(ddate.format("Today is %A, %B %d, %Y. %{ %N%nCelebrate %H!%}"))

