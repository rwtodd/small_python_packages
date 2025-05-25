from rwt.wikiapi import WikiSession
from rwt.wikidata import tarot
from pathlib import Path
import json

def gather_credentials(fname: str) -> dict[str,str]:
    """Get credentials from a json file"""
    with open(fname, "r") as read_file:
        data = json.load(read_file)
    if not set(data.keys()).issuperset({'uname','pw','url'}):
        raise SystemExit('Credentials must have "url", "uname", and "pw" entries!')
    return data

def push_one_document(ws: WikiSession, pname: str, srcdir: Path) -> None:
    fname = pname[6:].replace(' ','_') + '.wikitext'
    fpath = srcdir / fname
    print(f'pushing {pname} from {str(fpath)}')
    resp = ws.edit_from_file(str(fpath), 'updated file upload', pname)
    if not resp.ok:
        print(f'Bad response for {pname}')
        return

def push_cards(ws: WikiSession, srcdir: Path) -> None:
    deck = tarot.TarotDeck()
    for trumpnum in range(22):
        pname = deck.trump_bxref_page(trumpnum)
        push_one_document(ws, pname, srcdir)
    for s in tarot.Suit:
        for ct in tarot.Court:
            pname = deck.minor_bxref_page(s, ct)
            push_one_document(ws, pname, srcdir)
        for pip in range(1,11):
            pname = deck.minor_bxref_page(s, pip)
            push_one_document(ws, pname, srcdir)

def main(unpw : dict[str,str], srcdir: Path):
    with WikiSession(unpw['url']) as ws:
        rsp = ws.login(unpw['uname'], unpw['pw'])
        if not rsp.ok:
            print('failed to login')
            return
        push_cards(ws, srcdir)

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description="Push BXref tarot files from a mediawiki")
    parser.add_argument('-c','--credentials', type=str, default="un_pw.json", help="A JSON file of credentials (default: un_pw.json)")
    parser.add_argument('-s', '--srcdir', type=Path, default='.', help="the directory where the wikitext files are (default: .)")
    args = parser.parse_args()
    creds = gather_credentials(args.credentials)
    main(creds, args.srcdir)
