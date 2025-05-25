from rwt.wikiapi import WikiSession
from rwt.wikidata import tarot
import json

def gather_credentials(fname: str) -> dict[str,str]:
    """Get credentials from a json file"""
    with open(fname, "r") as read_file:
        data = json.load(read_file)
    if not set(data.keys()).issuperset({'uname','pw','url'}):
        raise SystemExit('Credentials must have "url", "uname", and "pw" entries!')
    return data

def pull_one_document(ws: WikiSession, pname: str) -> None:
    print(f'fetching {pname}')
    resp, wtxt = ws.fetch_wikitext(pname)
    if not resp.ok:
        print(f'Bad response for {pname}')
        return
    fname = pname[6:].replace(' ','_') + '.wikitext'
    with open(fname, 'w') as ofile:
        ofile.write(wtxt)

def pull_cards(ws: WikiSession) -> None:
    deck = tarot.TarotDeck()
    for trumpnum in range(22):
        pname = deck.trump_bxref_page(trumpnum)
        pull_one_document(ws, pname)
    for s in tarot.Suit:
        for ct in tarot.Court:
            pname = deck.minor_bxref_page(s, ct)
            pull_one_document(ws, pname)
        for pip in range(1,11):
            pname = deck.minor_bxref_page(s, pip)
            pull_one_document(ws, pname)

def main(unpw : dict[str,str]):
    with WikiSession(unpw['url']) as ws:
        rsp = ws.login(unpw['uname'], unpw['pw'])
        if not rsp.ok:
            print('failed to login')
            return
        pull_cards(ws)

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description="Pull BXref tarot files from a mediawiki")
    parser.add_argument('-c','--credentials', type=str, default="un_pw.json", help="A JSON file of credentials (default: un_pw.json)")
    args = parser.parse_args()
    creds = gather_credentials(args.credentials)
    main(creds)
