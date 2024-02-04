"""A module to take romanized versions of other alphabets and 
convert them to unicode.  The supported dialects are the hebrew
romanization used by English occultists of the 19th/20th centuries,
and a light form of betacode for greek."""

import re as _re
__all__ = ['hebrew','greek']

######################################################################
# Hebrew section
######################################################################
_hebtbl = {
  'A': "\u05d0", # alef
  'B': "\u05d1", # bet
  'G': "\u05d2", # gimel
  'D':  "\u05d3", # dalet,
  'H':  "\u05d4", # heh,
  'I':  "\u05d9", # yod,
  'L':  "\u05dc", # lamed,
  'O':  "\u05e2", # ayin,
  'Q':  "\u05e7", # qof,
  'R':  "\u05e8", # resh,
  'S':  "\u05e1", # samech,
  'T':  "\u05d8", # teth,
  'V':  "\u05d5", # vav,
  'Z':  "\u05d6", # zain,
  'Ch': "\u05d7", # cheth,
  'K':  "\u05db", # kaf initial,
  'Ki':  "\u05db", # kaf initial,
  'Kf':  "\u05da", # kaf final,
  'M':  "\u05de", # mem initial,
  'Mi':  "\u05de", # mem initial,
  'Mf':  "\u05dd", # mem final,
  'N':  "\u05e0", # nun initial,
  'Ni':  "\u05e0", # nun initial,
  'Nf':  "\u05df", # nun final,
  'P':  "\u05e4", # peh initial,
  'Pi':  "\u05e4", # peh initial,
  'Pf':  "\u05e3", # peh final,
  'Sh':  "\u05e9", # shin,
  'Th':  "\u05ea", # tav,
  'Tz':  "\u05e6", # tzaddi initial,
  'Tzi':  "\u05e6", # tzaddi initial,
  'Tzf':  "\u05e5", # tzaddi final,
  'Vv':  "\u05f0", # vav-vav ligature,
  'Vi':  "\u05f1", # vav-yod ligature,
  'Ii':  "\u05f2", # yod-yod ligature,
  ';':  "\u05b0", # Sh''va,
  ';3': "\u05b1", # Reduced Segol,
  ';_': "\u05b2", # Reduced Patach,
  ';7': "\u05b3", # Reduced Kamatz,
  '1': "\u05b4", # Hiriq,
  '2': "\u05b5", # Zeire,
  '3': "\u05b6", # Segol,
  '_': "\u05b7", # Patach,
  '7': "\u05b8", # Kamatz,
  '*': "\u05bc", # Dagesh,
  '\\': "\u05bb", # Kubutz,
  '`':  "\u05b9", # Holam,
  'l':  "\u05c2", # Dot Left,
  'r':  "\u05c1"  # Dot Right,
}

_nqudRx = r';[3_7]?|[123_7*\\`lr]'
_possFinRx = _re.compile(r'''
  (?>K|M|N|P|Tz) # a potential final letter
  (?=(?:{0})*+   # lookahead to a possible series of niqqud...
    (?:\W|\Z))   # ...and then a non-letter
  '''.format(_nqudRx), _re.X)
_tokensRx = _re.compile(r'''
  ((?>Ch|Sh|Tz|Th|Vv|[A-Z])[if]?+) # a letter
  ({0})?+ ({0})?+ ({0})?+          # up to 3 niqqud
  '''.format(_nqudRx), _re.X)

def hebrew(text):
    """Convert romanized `text` to unicode hebrew.
  A  = aleph   B  = beth    G  = gimel    D  = dalet
  H  = heh     V  = vav     Z  = zayin    Ch = chet
  T  = teth    I  = yod     K  = kaf      L  = lamed
  M  = mem     N  = nun     S  = samekh   O  = ayin
  P  = peh     Tz = tzaddi  Q  = qoph     R  = resh
  Sh = shin    Th = tav

  Ligatures:
  Ii = yod-yod   Vi = vav-yod     Vv = vav-vav

  Niqqud:
  ;  = Sh'va                *  = Dagesh
  \\ =  Kubutz              `  = Holam
  1  = Hiriq                2  = Zeire                
  3  = Segol                ;3 = Reduced Segol        
  _  = Patach               ;_ = Reduced Patach       
  7  = Kamatz               ;7 = Reduced Kamatz       
  Shl = Shin dot left       Shr = Shin dot right
"""
    finalized = _possFinRx.sub(r'\g<0>f',text)
    return _tokensRx.sub(
            lambda m: ''.join(_hebtbl.get(x,x) for x in m.groups() if x),
            finalized)

######################################################################
# Greek section
######################################################################

_grktbl = {
  '*A': "\u0391", 'A': "\u03b1", #alpha
  '*B': "\u0392", 'B': "\u03b2", #beta
  '*C': "\u039e", 'C': "\u03be", #xi
  '*D': "\u0394", 'D': "\u03b4", #delta
  '*E': "\u0395", 'E': "\u03b5", #epsilon
  '*F': "\u03a6", 'F': "\u03c6", #phi
  '*G': "\u0393", 'G': "\u03b3", #gamma
  '*H': "\u0397", 'H': "\u03b7", #eta
  '*I': "\u0399", 'I': "\u03b9", #iota
  '*K': "\u039a", 'K': "\u03ba", #kappa
  '*L': "\u039b", 'L': "\u03bb", #lambda
  '*M': "\u039c", 'M': "\u03bc", #mu
  '*N': "\u039d", 'N': "\u03bd", #nu
  '*O': "\u039f", 'O': "\u03bf", #omicron
  '*P': "\u03a0", 'P': "\u03c0", #pi
  '*Q': "\u0398", 'Q': "\u03b8", #theta
  '*R': "\u03a1", 'R': "\u03c1", #rho
  '*S': "\u03a3", 'S': "\u03c3", #sigma, medial sigma
  '*S1': "\u03a3", 'S1': "\u03c3", #sigma, medial sigma
  '*S2': "\u03a3", 'S2': "\u03c2", #sigma, final sigma
  '*S3': "\u03f9", 'S3': "\u03f2", #lunate sigma
  '*T': "\u03a4", 'T': "\u03c4", #tau
  '*U': "\u03a5", 'U': "\u03c5", #upsilon
  '*V': "\u03dc", 'V': "\u03dd", #digamma
  '*W': "\u03a9", 'W': "\u03c9", #omega
  '*X': "\u03a7", 'X': "\u03c7", #Chi
  '*Y': "\u03a8", 'Y': "\u03c8", #Psi
  '*Z': "\u0396", 'Z': "\u03b6", #Zeta
  # accents
  ')': "\u0313", #smooth breathing
  '(': "\u0314", #rough breathing
  '/': "\u0301", #acute
  '=': "\u0342", #circumflex (maybe use 302???)
  '\\': "\u0300", #grave
  '+': "\u0308", #diaeresis
  '|': "\u0345", #iota subscript
  '&': "\u0304", #macron
  '\'': "\u0306", #breve
  '?': "\u0323", #dot below
}

_graccRx = r"[()/=\\+|&'?]"
_sigmaFinalRx = _re.compile(r'''
  (?>S)         # a sigma
  (?=(?:{0})*+  # lookahead to a possible series of accents 
   (?:\W|\Z))   # ...and then a non-letter
  '''.format(_graccRx), _re.X)
_greekTokensRx = _re.compile(r'''
  (\*?+)    # UC indicator
  ({0}*+)   # possible accents
  ((?>[A-Z][123]?))   # letter
  ({0}*+)   # possible accents
  '''.format(_graccRx), _re.X)

def _greek_substitution(m):
    """Take the result of the _greekTokensRx regex match, and return the
    equivalent greek unicode"""
    letter = m.group(1) + m.group(3)
    return _grktbl.get(letter,letter) + ''.join(_grktbl.get(x,x) for x in (m.group(2)+m.group(4)))

def greek(text):
    """Convert betacode `text` to unicode greek. 
  *A/A  alpha         *B/B  beta
  *C/C  xi            *D/D  delta
  *E/E  epsilon       *F/F  phi
  *G/G  gamma         *H/H  eta
  *I/I  iota          *K/K  kappa
  *L/L  lambda        *M/M  mu
  *N/N  nu            *O/O  omicron
  *P/P  pi            *Q/Q  theta
  *R/R  rho           *S/S  sigma
  S1    medial sigma  S2  final sigma
  *S3/S3 lunate sigma *T/T  tau
  *U/U  upsilon       *V/V  digamma
  *W/W  omega         *X/X  Chi
  *Y/Y  Psi           *Z/Z  Zeta
  # accents
  )  smooth breathing (  rough breathing
  /  acute            =  circumflex
  \\  grave            +  diaeresis
  |  iota subscript   &  macron
  '  breve            ?  dot below
"""
    finalized = _sigmaFinalRx.sub(r'S2',text)
    return _greekTokensRx.sub(_greek_substitution, finalized)

