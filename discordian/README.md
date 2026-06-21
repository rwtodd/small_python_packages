# Discordian Date

A discordian date library/CLI in python.

```python
from rwt_discordian import DiscordianDate
import datetime

dd = DiscordianDate()  # today's date
print(f"{dd:%X days til X-day!}")

dd2 = DiscordianDate(datetime.date(1981, 1, 21))
print(dd2)
```

## Test

Test with:

```bash
uv run python -m unittest discover -v -s tests
```

## Installation

### As a library

```bash
uv pip install .
# or
pip install .
```

### The `ddate` CLI tool

```bash
uv tool install .

ddate
ddate -f "%Y YOLD"
```

After installation the `ddate` command is on your `$PATH`.

## Format Strings

The program takes all the normal %-replacements from the linux `ddate(1)` utility.

```
Format Strings: (e.g.,  "Today is %{%A, the %E of %B%}!")
   %A  weekday        /  %a  weekday (short version)
   %B  season         /  %b  season (short version)
   %d  day of season  /  %e  ordinal day of season
   %Y  the Year of Our Lady of Discord
   %X  the number of days left until X-Day

   %H  name of the holy day, if it is one
   %N  directive to skip the rest of the format
       if today is not a holy day

   %{ ... %}  either announce Tibs Day, or format the
              interior string if it is not Tibs Day

   %n  newline        /  %t  tab
```
