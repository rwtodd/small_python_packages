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
    KING = 1   # The old masculine, in some decks this is the Knight
    QUEEN = 2
    PRINCE = 3 # The young masculine, in some decks this is the King when the Knight is the 'father'
    PRINCESS = 4

_Generic_Trumps = ['The Fool', 
                   'The Magician', 'The High Priestess', 'The Empress', 'The Emperor', 'The Hierophant', 'The Lovers', 'The Chariot',
                   'Strength', 'The Hermit', 'Wheel of Fortune', 'Justice', 'The Hanged Man', 'Death', 'Temperance',
                   'The Devil', 'The Tower', 'The Star', 'The Moon', 'The Sun', 'Judgement', 'The World']
_Generic_Minors = ['Ace', 'Two', 'Three', 'Four', 'Five', 'Six', 'Seven', 'Eight', 'Nine', 'Ten']
_Generic_Royals = ['Knight', 'Queen', 'King', 'Page']  # RWS-Style decks.

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
            case Court.KING:
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

    def trump_wikipage_name(self, num: int) -> str:
        """Give the name of the page for the trump"""
        pn = self.trump_name(num)
        if pn.startswith('The '):
            pn = pn[4:] + ', The'
        return pn
    
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

class JungianTarot(TarotDeck):
    """Specific responses for the Jungian Tarot."""
    _JUNGIAN_ROYALS = ['King', 'Queen', 'Prince', 'Princess']

    def _trump_name_fixup(self, tn: str) -> str:
        """Correct the generic trump names for the Jungian Tarot"""
        if tn.endswith('Lovers'):
            tn = tn[:-1]
        elif tn == 'Judgement':
            tn = 'Judgment'
        return tn
    
    def trump_name(self, num:int) -> str:
        return self._trump_name_fixup(self._generic_trump_name(num))

    def minor_name(self, suit: Suit, card: Court|int) -> str:
        match card:
            case Court():
                card_name = JungianTarot._JUNGIAN_ROYALS[card.value - 1]
            case int(n) if 1 <= n <= 10:
                card_name = _Generic_Minors[n - 1]
            case _:
                raise ValueError('tarot minor cards are 1-10 or a Court.XXX!')
        return f'{card_name} of {suit.name.capitalize()}'

    def trump_image_url(self, num: int) -> str:
        """Get the image name for a given trump card (e.g. JungianTarot_Fool.webp)"""
        base = self._trump_name_fixup(self._generic_trump_imagebase(num))
        return f'JungianTarot_{base}.webp'

    def minor_image_url(self, suit: Suit, card: Court|int) -> str:
        """Get the image name for a given trump card (e.g. RWSTarot_4oCups.jpeg)"""
        match card:
            case Court.KING:
                cname = 'K'
            case Court.QUEEN:
                cname = 'Q'
            case Court.PRINCE:
                cname = 'P'
            case Court.PRINCESS:
                cname = 'Ps'
            case 1:
                cname = 'A'
            case int(n) if 2 <= n <= 10:
                cname = str(n)
            case _:
                raise ValueError('tarot minor cards are 1-10 or a Court.XXX!')
        return f'JungianTarot_{cname}o{suit.name.capitalize()}.webp'

class ThothTarotDeck(TarotDeck):
    """Specific responses for the Thoth tarot. For consistency, Strength is still 8 despite what the physical deck says."""
    _THOTH_TRUMPS = ['The Fool', 
                   'The Magus', 'The Priestess', 'The Empress', 'The Empereor', 'The Hierophant', 'The Lovers', 'The Chariot',
                   'Lust', 'The Hermit', 'Fortune', 'Adjustment', 'The Hanged Man', 'Death', 'Art',
                   'The Devil', 'The Tower', 'The Star', 'The Moon', 'The Sun', 'The Aeon', 'The Universe']
    _THOTH_ROYALS = [ 'Knight', 'Queen', 'Prince', 'Princess' ]

    def trump_name(self, num:int) -> str:
        """Get the name of the given trump card."""
        if 0 <= num <= 21:
            return ThothTarotDeck._THOTH_TRUMPS[num]
        else:
            raise ValueError('Trumps are from 0 to 21!')

    def minor_name(self, suit: Suit, card: Court|int) -> str:
        """slightly different than a generic deck"""
        match card:
            case Court():
                card_name = ThothTarotDeck._THOTH_ROYALS[card.value - 1]
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

class BotaTarotDeck(TarotDeck):
    """The BOTA deck only really contains trumps (as far as I am concerned...)"""
    def trump_image_url(self, num: int) -> str:
        """Get the BOTA painted trump image"""
        if 0 <= num <= 21:
            return f'BOTA_Key_{num}_Painted.jpg'
        raise ValueError('Trump number should be between 0 and 21!')

class HaindlTarotDeck(TarotDeck):
    """The Haindl Deck"""

    _HAINDL_TRUMPS = ['The Fool', 
                   'The Magician', 'The High Priestess', 'The Empress', 'The Empereor', 'The Hierophant', 'The Lovers', 'The Chariot',
                   'Lust', 'The Hermit', 'The Wheel of Fortune', 'Justice', 'The Hanged Man', 'Death', 'Alchemy',
                   'The Devil', 'The Tower', 'The Star', 'The Moon', 'The Sun', 'Aeon', 'The Universe']
  
    def trump_name(self, num:int) -> str:
        """Get the name of the given trump card."""
        if 0 <= num <= 21:
            return HaindlTarotDeck._HAINDL_TRUMPS[num]
        else:
            raise ValueError('Trumps are from 0 to 21!')

    def minor_name(self, suit: Suit, card: Court|int) -> str:
        """slightly different than a generic deck... Father = King (Prince)"""
        match card:
            case Court.KING:
                card_name = "Son"
            case Court.QUEEN:
                card_name = "Mother"
            case Court.PRINCE:
                card_name = "Father"
            case Court.PRINCESS:
                card_name = "Daughter"
            case int(n) if 1 <= n <= 10:
                card_name = _Generic_Minors[n - 1]
            case _:
                raise ValueError('tarot minor cards are 1-10 or a Cour.XXX!')
        match suit:
            case Suit.PENTACLES:
                suit_name = 'Stones'
            case _:
                suit_name = suit.name.capitalize()
        return f'{card_name} of {suit_name}'

    def trump_image_url(self, num:int) -> str:
        """Get the Haindl deck trump image"""
        if 0 <= num <= 21:
            return f'HaindlTarotTrump{num:02d}.jpg'
        raise ValueError('Trump number should be between 0 and 21!')

    def minor_image_url(self, suit: Suit, card: Court|int) -> str:
        match card:
            case Court.KING:
                cname = 'Kn'
            case Court.QUEEN:
                cname = 'Qn'
            case Court.PRINCE:
                cname = 'Kg'
            case Court.PRINCESS:
                cname = 'Pg'
            case 1:
                cname = 'Ace'
            case int(x) if 2 <= x <= 10:
                cname = str(x)
            case _:
                raise ValueError(f'<{card}> is not a valid tarot card')
        match suit:
            case Suit.PENTACLES:
                sname = 'Stones'
            case _:
                sname = suit.name.capitalize()
        return f"HaindlTarot{cname}{sname}.jpg"
        