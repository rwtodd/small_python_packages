# tarot data from the wiki:
# For each tarot card:
# - BXref:  link for the xref table
#
# For each tarot deck:
# - card image URLs
#
# For each tarot book:
# - book 'type'
# - card-specific chapter/section URLs
#
# ~~~~~~~~~~~~
from enum import Enum as _Enum

class Suit(_Enum):
    WANDS = 1
    CUPS = 2
    SWORDS = 3
    PENTACLES = 4

class Court(_Enum):
    KNIGHT = 1
    QUEEN = 2
    PRINCE = 3
    PRINCESS = 4

_Generic_Trumps = ['The Fool', 
                   'The Magician', 'The High Priestess', 'The Empress', 'The Empereor', 'The Hierophant', 'The Lovers', 'The Chariot',
                   'Strength', 'The Hermit', 'Wheel of Fortune', 'Justice', 'The Hanged Man', 'Death', 'Temperance',
                   'The Devil', 'The Tower', 'The Star', 'The Moon', 'The Sun', 'Judgement', 'The World']
_Generic_Minors = ['Ace', 'Two', 'Three', 'Four', 'Five', 'Six', 'Seven', 'Eight', 'Nine', 'Ten']
_Generic_Royals = ['Knight', 'Queen', 'King', 'Page']

class TarotDeck:
    """Generic tarot card info, generally follows RWS"""
    def _generic_trump_name(self, num: int) -> str:
        if 0 <= num <= 21:
            return _Generic_Trumps[num]
        else:
            raise ValueError('Trumps are from 0 to 21!')

    def _generic_minor_name(self, suit: Suit, card : Court|int) -> str:
        match card:
            case Court():
                card_name = _Generic_Royals[card.value - 1]
            case int(n) if 1 <= n <= 10:
                card_name = _Generic_Minors[n - 1]
            case _:
                raise ValueError('tarot minor cards are 1-10 or a Court.XXX!')
        return f'{card_name} of {suit.name.capitalize()}'
    
    def _generic_trump_imagebase(self, num: int) -> str:
        """Get the base of the image name for a given trump card (e.g. File:RWSTarot_Fool.jpeg is Fool)"""
        tname = self._generic_trump_name(num)
        if tname.startswith('The '):
            tname = tname[4:]
        else:
            tname = tname.title()
        return tname.replace(' ', '')

    def _generic_minor_imagebase(self, suit: Suit, card: Court|int) -> str:
        """Get the base of the card images common to at least RWS and Thoth, and maybe others."""
        match card:
            case Court.KNIGHT:
                cname = 'N'
            case Court.QUEEN:
                cname = 'Q'
            case Court.PRINCE:
                cname = 'K'
            case Court.PRINCESS:
                cname = 'P'
            case 1:
                cname = 'A'
            case int(n) if 2 <= n <= 10:
                cname = str(n)
            case _:
                raise ValueError('tarot minor cards are 1-10 or a Court.XXX!')
        return f'{cname}o{suit.name.capitalize()}'

    def trump_name(self, num:int) -> str:
        """Get the name of the given trump card."""
        return self._generic_trump_name(num)

    def minor_name(self, suit: Suit, card: Court|int) -> str:
        """Get the name of the given minor card"""
        return self._generic_minor_name(suit, card)
    
    def trump_bxref_page(self, num: int) -> str:
        """Get the BXref page for the given trump card"""
        tname = self._generic_trump_name(num)
        if tname.startswith('The '):
            tname = tname[4:]
        return f'BXref:{tname} (Tarot Card)'

    def minor_bxref_page(self, suit: Suit, card: Court|int) -> str:
        """Get the BXref page for the given minor card"""
        cname = self._generic_minor_name(suit, card)
        return f'BXref:{cname} (Tarot Card)'
    
    def trump_image_url(self, num: int) -> str:
        """Get the image name for a given trump card (e.g. RWSTarot_Fool.jpeg)"""
        base = self._generic_trump_imagebase(num)
        return f'RWSTarot_{base}.jpeg'

    def minor_image_url(self, suit: Suit, card: Court|int) -> str:
        """Get the image name for a given trump card (e.g. RWSTarot_4oCups.jpeg)"""
        base = self._generic_minor_imagebase(suit, card)
        return f'RWSTarot_{base}.jpeg'

class RWSTarotDeck(TarotDeck):
    pass # this _is_ the Generic tarot!

class ThothTarotDeck(TarotDeck):
    """Specific responses for the Thoth tarot. For consistency, Strength is still 8 despite what the physical deck says."""
    _THOTH_TRUMPS = ['The Fool', 
                   'The Magus', 'The Priestess', 'The Empress', 'The Empereor', 'The Hierophant', 'The Lovers', 'The Chariot',
                   'Lust', 'The Hermit', 'Fortune', 'Adjustment', 'The Hanged Man', 'Death', 'Art',
                   'The Devil', 'The Tower', 'The Star', 'The Moon', 'The Sun', 'The Aeon', 'The Universe']
 
    def trump_name(self, num:int) -> str:
        """Get the name of the given trump card."""
        if 0 <= num <= 21:
            return ThothTarotDeck._THOTH_TRUMPS[num]
        else:
            raise ValueError('Trumps are from 0 to 21!')

    def minor_name(self, suit: Suit, card: Court|int) -> str:
        """slightly different than a generic deck"""
        match card:
            case Suit():
                card_name = suit.name.capitalize()
            case int(n) if 1 <= n <= 10:
                card_name = _Generic_Minors[n - 1]
            case _:
                raise ValueError('tarot minor cards are 1-10 or a Cour.XXX!')
        match suit:
            case Suit.PENTACLES:
                suit_name = 'Disks'
            case _:
                suit_name = suit.name.capitalize()
        return f'{card_name} of {suit_name}'

    def trump_image_url(self, num: int) -> str:
        """Get the image name for a given trump card (e.g. ThothTarot_Fool.webp)"""
        base = self._generic_trump_imagebase(num)
        return f'ThothTarot_{base}.webp'

    def minor_image_url(self, suit: Suit, card: Court|int) -> str:
        """Get the image name for a given trump card (e.g. ThothTarot_4oCups.webp)"""
        base = self._generic_minor_imagebase(suit, card)
        return f'ThothTarot_{base}.webp'

