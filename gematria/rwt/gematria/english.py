import string as _string
import itertools as _itertools
from collections import defaultdict as _defaultdict

_named = {
  'alw': 
    [1, 20, 13, 6, 25, 18, 11, 4, 23, 16, 9, 2, 21, 14, 7, 26, 19, 12, 5, 24, 17, 10, 3, 22, 15, 8],
  'love-x':
    [9, 20, 13, 6, 17, 2, 19, 12, 23, 16, 1, 18, 5, 22, 15, 26, 11, 4, 21, 8, 25, 10, 3, 14, 7, 24],
  'liber-cxv':
    [1, 5, 9, 12, 2, 8, 10, 0, 3, 6, 9, 14, 6, 13, 4, 7, 18, 15, 16, 11, 5, 8, 10, 11, 6, 32],
  'leeds':
    [1, 2, 3, 4, 5, 6, 7, 6, 5, 4, 3, 2, 1, 1, 2, 3, 4, 5, 6, 7, 6, 5, 4, 3, 2, 1],
  'simple':
    range(1,27),
  'liber-a':
    range(26),
  'trigrammaton':
    [5, 20, 2, 23, 13, 12, 11, 3, 0, 7, 17, 1, 21, 24, 10, 4, 16, 14, 15, 9, 25, 22, 8, 6, 18, 19]
}

def cipher_names():
  """Get a list of all pre-defined cipher names which can be used to create a Cipher"""
  return _named.keys()

def lexicon_synonyms(lexicon):
  """Take a lexicon--a dict of words to cipher-sums--and generate the inverse dict, which maps sums
  to list of words with that sum. These are cipher synonyms, and are really the point of gematria."""
  result = _defaultdict(list)
  for w in sorted(lexicon): 
    result[lexicon[w]].append(w)
  return result

def print_synonyms(synonyms, file=None):
  """Take a dict of synonyms (such as provided by the `lexicon_synonyms` function), and print out
  a formatted dictionary of synonyms."""
  for num in sorted(synonyms):
    print(f"{num}:",file=file)
    for word in synonyms[num]:
      print(f"  {word}",file=file)

class Cipher:
  def __init__(self, dictionary):
    """Create a Cipher with either a name of a pre-defined cipher, or with a dict from letters
    to numeric values."""
    if isinstance(dictionary,str):
      values = _named[dictionary]
      # todo.. throw error if not found!
      dictionary = { k: v for (k,v) in zip(_string.ascii_letters, _itertools.cycle(values)) }
      dictionary['-'] = dictionary["'"] = 0
    self.__code = dictionary

  def sum(self, word):
    """Compute the sum for a string, according to the cipher."""
    return sum(self.__code.get(ch,0) for ch in word)

  def describe(self, file=None):
    """Print out a description of the cipher to the desired file (defaults to sys.stdout)."""
    count = 0
    for uc in _string.ascii_uppercase:
      count += 1
      val,lcval = self.__code.get(uc,0), self.__code.get(uc.lower(),0)
      vstr = str(val) if val == lcval else f'{val}/{lcval}'
      print(f'{uc}: {vstr}', file=file, end='\n' if count % 5 == 0 else '\t')
    for nonlet,val in (item for item in self.__code.items() if not (item[0].isascii() and item[0].isalpha())):
      count += 1
      print(f'{nonlet}: {val}', file=file, end='\n' if count % 5 == 0 else '\t')
    if count % 5 != 0:
      print(file=file)

  def add_to_lexicon(self, lexicon, words):
    """Add sums for every given word in WORDS to the dict in LEXICON"""
    for w in words:
      lexicon[w] = self.sum(w)

  def split_into_lexicon(self, lexicon, text):
    """Split words based on each character's presence in the Cipher, and add each of the words to
    the given dict LEXICON"""
    self.add_to_lexicon(lexicon, text.split()) # todo, split using actual Cipher

